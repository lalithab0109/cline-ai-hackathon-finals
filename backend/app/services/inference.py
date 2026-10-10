"""Inference boundary between the API and the (future) ML pipeline.

This module is the single seam where mock inference will be replaced by the
real OpenCV -> SVR -> SVM pipeline developed in the `ml/` package. The API
contract (`schemas.ScanAnalysisResponse`) stays identical either way, so no
frontend change will be required.

Planned real implementation (roadmap section 8.4):

    def analyze_strip(image_bytes, test_type, patient_info, scan_id):
        # 1. Validate and inspect image
        # 2. Detect strip, calibrate, extract features (OpenCV)
        # 3. Reject poor-quality scans (quality gate)
        # 4. Run experimental SVR estimate (scikit-learn)
        # 5. Run experimental SVM classification (scikit-learn)
        # 6. Return versioned, explainable structured result

Current behaviour: delegates to the deterministic mock service. Routers must
call ONLY this adapter, never the mock directly.
"""

from __future__ import annotations

from typing import Optional

from ..schemas import ScanAnalysisResponse, TestType
from . import mock_inference

# "mock" until the ML pipeline in `ml/` is integrated behind this adapter.
INFERENCE_MODE = "mock"

# Re-exported for the metadata endpoints (health, models/info).
MOCK_MODEL = mock_inference.MOCK_MODEL


def analyze_strip(
    *,
    image_bytes: bytes,
    test_type: TestType,
    scan_id: str,
    patient_age: int,
    patient_sex: Optional[str],
) -> ScanAnalysisResponse:
    """Unified inference interface (currently mock-backed).

    When the real ML pipeline lands, this function will call
    `ml.analyze_strip(...)` instead of the mock service, returning the same
    response schema.
    """

    # `image_bytes` is intentionally unused in mock mode: the mock must never
    # claim measurements were extracted from the uploaded image.
    del image_bytes
    return mock_inference.build_mock_result(
        scan_id=scan_id,
        test_type=test_type,
        age=patient_age,
        sex=patient_sex,
    )


def build_quality_failure(
    *, scan_id: str, test_type: TestType, issues: list[str]
) -> ScanAnalysisResponse:
    """Failed-quality response for uploads that fail validation."""

    return mock_inference.build_failed_result(
        scan_id=scan_id, test_type=test_type, issues=issues
    )
