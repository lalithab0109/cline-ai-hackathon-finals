"""Shared Pydantic request/response schemas for the Aarogya Bindu API.

These models define the STABLE API contract agreed before ML integration
(see Aarogya_Bindu_Development_and_ML_Roadmap.md, section 6). The frontend
must be able to consume these responses whether inference is mocked or
backed by the real OpenCV -> SVR -> SVM pipeline.

Contract rules encoded here:
- Every analysis response carries `source`, `clinically_validated`, and
  explicit `is_simulated` flags on measurement/classification.
- `measurement` and `classification` are nullable: failed-quality scans must
  never receive a fabricated result.
- Model identifier and version are always reported for provenance.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TestType(str, Enum):
    """Diagnostic screening tests supported by the application."""

    HEMOGLOBIN = "hemoglobin"
    GLUCOSE = "glucose"
    URINE_ALBUMIN = "urine_albumin"


class SampleType(str, Enum):
    """Biological sample the test strip is designed for."""

    BLOOD = "blood"
    URINE = "urine"


class DataSource(str, Enum):
    """Provenance of the analysis data.

    - MOCK: deterministic placeholder used during development.
    - SYNTHETIC: produced from synthetic images / experimental models.
    - VALIDATED: backed by clinically validated data (never used yet).
    """

    MOCK = "mock"
    SYNTHETIC = "synthetic"
    VALIDATED = "validated"


class ScanStatus(str, Enum):
    """Outcome status of a scan analysis request."""

    SUCCESS = "success"
    QUALITY_FAILED = "quality_failed"
    ERROR = "error"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    inference_mode: Literal["mock", "ml"]


class TestMetadata(BaseModel):
    """Public metadata describing one supported screening test."""

    id: TestType
    name: str
    sample_type: SampleType
    unit: str
    description: str
    # Plain-language note about what the screening can and cannot show.
    interpretation_note: str


class TestsResponse(BaseModel):
    tests: list[TestMetadata]
    disclaimer: str


class ModelDescriptor(BaseModel):
    """Identifier and version of an inference component, for provenance."""

    identifier: str
    version: str
    kind: Literal["mock", "svr", "svm", "opencv"]


class ModelsInfoResponse(BaseModel):
    """Describes the inference stack currently backing the API."""

    inference_mode: Literal["mock", "ml"]
    clinically_validated: bool = False
    active_models: list[ModelDescriptor]
    # The planned real pipeline, documented for integrators.
    planned_pipeline: list[str]
    notes: str
    disclaimer: str


class PatientCreate(BaseModel):
    """Request body for POST /api/patients (demo/fictional patients only)."""

    age: int = Field(ge=0, le=120)
    sex: Optional[Literal["female", "male", "other"]] = None
    demo_identifier: Optional[str] = Field(
        default=None,
        description="Optional label for the fictional demo session (e.g. 'demo-patient-1').",
    )


class PatientResponse(BaseModel):
    patient_id: str
    age: int
    sex: Optional[str] = None
    demo_identifier: Optional[str] = None
    created_at: str



# ---------------------------------------------------------------------------
# Scan analysis contract (roadmap section 6)
# ---------------------------------------------------------------------------


class QualityResult(BaseModel):
    """Image quality assessment gate for a scan."""

    passed: bool
    blur_score: Optional[float] = None
    calibration_detected: Optional[bool] = None
    calibration_error: Optional[float] = None
    # Actionable issues for the patient when quality fails
    # (e.g. "retake in brighter light").
    issues: list[str] = Field(default_factory=list)


class ImageAnalysis(BaseModel):
    """Colorimetric features extracted from the strip reaction pad."""

    mean_rgb: Optional[list[float]] = Field(default=None, min_length=3, max_length=3)
    mean_lab: Optional[list[float]] = Field(default=None, min_length=3, max_length=3)
    synthetic_intensity: Optional[float] = None
    annotated_image_url: Optional[str] = None


class Measurement(BaseModel):
    """Estimated biomarker measurement. Always flagged when simulated."""

    value: float
    unit: str
    method: str = Field(description="Estimator used, e.g. 'mock', 'svr'.")
    is_simulated: bool = True


class Classification(BaseModel):
    """Illustrative screening severity classification. Never a diagnosis."""

    label: str
    method: str = Field(description="Classifier used, e.g. 'mock_svm_demo', 'svm'.")
    is_simulated: bool = True


class Explanation(BaseModel):
    """Explainability payload: evidence, inputs, and honest limitations."""

    summary: str
    inputs_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScanAnalysisResponse(BaseModel):
    """Stable response contract for POST /api/scans/analyze.

    `measurement` and `classification` are null when the scan fails quality
    checks or errors; the UI must render the retry/error state instead.
    """

    scan_id: str
    report_id: Optional[str] = None
    test_type: TestType
    status: ScanStatus
    source: DataSource
    clinically_validated: bool = False
    model: ModelDescriptor
    quality: QualityResult
    image_analysis: Optional[ImageAnalysis] = None
    measurement: Optional[Measurement] = None
    classification: Optional[Classification] = None
    explanation: Explanation
    disclaimer: str


class ScreeningHistoryEntry(BaseModel):
    scan_id: str
    report_id: Optional[str] = None
    test_type: TestType
    status: ScanStatus
    created_at: str


class ScreeningHistoryResponse(BaseModel):
    patient_id: str
    entries: list[ScreeningHistoryEntry]
    disclaimer: str
