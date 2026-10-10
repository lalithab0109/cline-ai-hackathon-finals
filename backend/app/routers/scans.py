"""POST /api/scans/analyze — upload handling and scan orchestration.

Validation order: patient exists -> content type -> size limit -> image
integrity (Pillow decode check). Any failure produces a persisted
`quality_failed` scan with NO measurement or classification, per the API
contract. Successful uploads go through the inference adapter (mock today,
OpenCV -> SVR -> SVM later) without the router knowing the difference.
"""

from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from .. import database
from ..config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES
from ..schemas import ScanAnalysisResponse, TestType
from ..services import inference

router = APIRouter(tags=["scans"])

_MAX_IMAGE_MB = MAX_IMAGE_BYTES // (1024 * 1024)


@router.post("/scans/analyze", response_model=ScanAnalysisResponse)
async def analyze_scan(
    image: UploadFile = File(...),
    test_type: TestType = Form(...),
    patient_id: str = Form(...),
) -> ScanAnalysisResponse:
    patient = database.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    issues = _validate_image_metadata(image)
    image_bytes = b""

    if not issues:
        image_bytes, size_issue = await _read_with_limit(image)
        if size_issue:
            issues.append(size_issue)

    if not issues:
        issues = _verify_image_integrity(image_bytes, image.content_type)

    # Persist every attempt: failed scans are part of the demo record too.
    session = database.create_session(
        patient_id=patient_id,
        test_type=test_type.value,
        status="quality_failed" if issues else "success",
    )

    if issues:
        result = inference.build_quality_failure(
            scan_id=session["id"], test_type=test_type, issues=issues
        )
    else:
        result = inference.analyze_strip(
            image_bytes=image_bytes,
            test_type=test_type,
            scan_id=session["id"],
            patient_age=patient["age"],
            patient_sex=patient["sex"],
        )

    database.save_analysis(session["id"], result)
    return result


def _validate_image_metadata(image: UploadFile) -> list[str]:
    if (image.content_type or "").lower() not in ALLOWED_IMAGE_TYPES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_TYPES))
        return [
            f"Unsupported file type '{image.content_type}'. "
            f"Please upload one of: {allowed}."
        ]
    return []


async def _read_with_limit(image: UploadFile) -> tuple[bytes, str | None]:
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        return b"", (
            f"The image is larger than {_MAX_IMAGE_MB} MB. "
            "Please retake or compress the photo and try again."
        )
    if not data:
        return b"", "The uploaded file is empty. Please choose a photo of the test strip."
    return data, None


def _verify_image_integrity(data: bytes, claimed_type: str | None) -> list[str]:
    """Decode-check the upload with Pillow (no feature extraction here)."""

    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
            detected = (img.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError):
        return [
            "The file could not be read as a valid image. "
            "Please retake the photo and try again."
        ]

    expected = {
        "image/jpeg": {"JPEG"},
        "image/png": {"PNG"},
        "image/webp": {"WEBP"},
    }.get(claimed_type or "", set())
    if expected and detected not in expected:
        return [
            "The file contents do not match its declared image type. "
            "Please upload the original photo."
        ]
    return []
