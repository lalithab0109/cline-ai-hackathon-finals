"""GET /api/tests — metadata for the supported screening tests.

The metadata is static for the prototype. Units and sample types are
test-specific and must stay consistent with future inference output
(urine albumin is a URINE test; never mix units across tests).
"""

from fastapi import APIRouter

from ..config import SIMULATION_DISCLAIMER
from ..schemas import SampleType, TestMetadata, TestsResponse, TestType

router = APIRouter(tags=["tests"])

SUPPORTED_TESTS: list[TestMetadata] = [
    TestMetadata(
        id=TestType.HEMOGLOBIN,
        name="Hemoglobin",
        sample_type=SampleType.BLOOD,
        unit="g/dL",
        description=(
            "Preliminary anemia-style screening from a blood-based "
            "colorimetric test strip."
        ),
        interpretation_note=(
            "Demonstration estimates illustrate the screening workflow only; "
            "they cannot diagnose anemia or rule it out."
        ),
    ),
    TestMetadata(
        id=TestType.GLUCOSE,
        name="Glucose",
        sample_type=SampleType.BLOOD,
        unit="mg/dL",
        description=(
            "Preliminary glucose screening using a compatible blood-based "
            "colorimetric assay strip."
        ),
        interpretation_note=(
            "Demonstration estimates illustrate the screening workflow only; "
            "they cannot diagnose diabetes or rule it out."
        ),
    ),
    TestMetadata(
        id=TestType.URINE_ALBUMIN,
        name="Urine Albumin",
        sample_type=SampleType.URINE,
        unit="mg/L",
        description=(
            "Preliminary urine albumin screening from a urine-based "
            "colorimetric test strip."
        ),
        interpretation_note=(
            "Demonstration estimates illustrate the screening workflow only; "
            "they cannot diagnose kidney disease or rule it out."
        ),
    ),
]


@router.get("/tests", response_model=TestsResponse)
def get_tests() -> TestsResponse:
    return TestsResponse(tests=SUPPORTED_TESTS, disclaimer=SIMULATION_DISCLAIMER)
