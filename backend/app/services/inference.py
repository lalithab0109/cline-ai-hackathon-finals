"""Inference boundary between the API and the ML pipeline.

Routers call ONLY this adapter. Routing by test type:

- hemoglobin     -> trained SVR via `ml_hemoglobin` (OpenCV preprocessing +
                    feature extraction live in `ml/aarogya-bindu-ml`; nothing
                    is duplicated here). If the model cannot load,
                    `MLUnavailableError` propagates - hemoglobin NEVER falls
                    back to mock values.
- glucose,
  urine_albumin  -> deterministic mock fixtures (no trained models yet).

The API contract (`schemas.ScanAnalysisResponse`) is identical for both paths.
"""

from __future__ import annotations

from typing import Literal, Optional

from ..schemas import ScanAnalysisResponse, TestType
from . import mock_inference, ml_hemoglobin
from .ml_hemoglobin import MLUnavailableError

__all__ = [
    "INFERENCE_MODE",
    "MOCK_MODEL",
    "MLUnavailableError",
    "analyze_strip",
    "build_quality_failure",
    "ml_status",
    "startup_check",
    "svm_status",
    "test_backends",
    "test_classifiers",
]

# Hemoglobin is ML-backed; glucose and urine albumin remain mock.
INFERENCE_MODE: Literal["hybrid"] = "hybrid"

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
    """Unified inference interface.

    Raises MLUnavailableError for hemoglobin when the trained model cannot be
    loaded (the router turns this into HTTP 503; it is never mocked).
    """

    if test_type == TestType.HEMOGLOBIN:
        # patient age/sex are not used by the hemoglobin model.
        return ml_hemoglobin.analyze(image_bytes=image_bytes, scan_id=scan_id)

    # Glucose / urine albumin: deterministic mock. `image_bytes` is
    # intentionally unused - the mock must never claim values came from the
    # uploaded image.
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
    """Failed-scan response for uploads rejected by the router's file checks."""

    return mock_inference.build_failed_result(
        scan_id=scan_id, test_type=test_type, issues=issues
    )


def startup_check() -> None:
    """Load the hemoglobin model at startup; raises MLUnavailableError."""
    ml_hemoglobin.load()


def ml_status() -> tuple[bool, Optional[str]]:
    """(hemoglobin model available, reason if not)."""
    return ml_hemoglobin.is_available()


def svm_status() -> tuple[bool, Optional[str]]:
    """(demonstration SVM available, reason if not); False if the SVR is down."""
    try:
        return ml_hemoglobin.svm_status()
    except MLUnavailableError as exc:
        return False, str(exc)


def test_classifiers() -> dict[str, Literal["ml", "mock", "unavailable"]]:
    """Which classifier serves each test (reported by /api/models/info)."""
    available, _ = svm_status()
    return {
        TestType.HEMOGLOBIN.value: "ml" if available else "unavailable",
        TestType.GLUCOSE.value: "mock",
        TestType.URINE_ALBUMIN.value: "mock",
    }


def test_backends() -> dict[str, Literal["ml", "mock", "unavailable"]]:
    """Which backend serves each test (reported by /api/models/info)."""
    available, _ = ml_status()
    return {
        TestType.HEMOGLOBIN.value: "ml" if available else "unavailable",
        TestType.GLUCOSE.value: "mock",
        TestType.URINE_ALBUMIN.value: "mock",
    }
