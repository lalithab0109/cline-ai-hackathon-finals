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
    # "hybrid" = hemoglobin uses the trained synthetic-data ML model while the
    # other tests still use deterministic mock inference.
    inference_mode: Literal["mock", "ml", "hybrid"]


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

    inference_mode: Literal["mock", "ml", "hybrid"]
    clinically_validated: bool = False
    active_models: list[ModelDescriptor]
    # The real pipeline stages, documented for integrators.
    planned_pipeline: list[str]
    notes: str
    disclaimer: str
    # Per-test inference backend: "ml", "mock", or "unavailable" (never a
    # silent fallback to mock when a model fails to load).
    test_inference: dict[str, Literal["ml", "mock", "unavailable"]] = Field(
        default_factory=dict
    )
    # Per-test classifier backend: "ml" (demonstration SVM), "mock", or
    # "unavailable" (scan still returns the value, with classification null).
    test_classification: dict[str, Literal["ml", "mock", "unavailable"]] = Field(
        default_factory=dict
    )


class PatientCreate(BaseModel):
    """Request body for POST /api/patients (demo/fictional patients only)."""

    age: int = Field(ge=0, le=120)
    sex: Optional[Literal["female", "male", "other"]] = None
    display_name: Optional[str] = Field(
        default=None,
        max_length=80,
        description="Optional fictional display name for the demo profile.",
    )


class PatientResponse(BaseModel):
    patient_id: str
    age: int
    sex: Optional[str] = None
    display_name: Optional[str] = None
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
    # Additional numeric quality evidence from the image pipeline (e.g.
    # clipping fraction, paper brightness, ROI size). Empty for mock results.
    metrics: dict[str, float] = Field(default_factory=dict)


class RoiDetection(BaseModel):
    """Where the pipeline found the reaction area (pixel coordinates)."""

    method: str
    confidence: float
    # Four (x, y) corners ordered TL, TR, BR, BL.
    corners_xy: list[list[float]] = Field(default_factory=list)


class ImageAnalysis(BaseModel):
    """Colorimetric features extracted from the strip reaction pad."""

    mean_rgb: Optional[list[float]] = Field(default=None, min_length=3, max_length=3)
    mean_lab: Optional[list[float]] = Field(default=None, min_length=3, max_length=3)
    synthetic_intensity: Optional[float] = None
    annotated_image_url: Optional[str] = None
    roi_detection: Optional[RoiDetection] = None


class Measurement(BaseModel):
    """Estimated biomarker measurement. Always flagged when simulated."""

    value: float
    unit: str
    method: str = Field(description="Estimator used, e.g. 'mock', 'svr'.")
    is_simulated: bool = True


class Classification(BaseModel):
    """Illustrative screening severity classification. Never a diagnosis."""

    label: str
    method: str = Field(
        description="Classifier used, e.g. 'mock_svm_demo', 'svm_synthetic_demo'."
    )
    is_simulated: bool = True
    # Provenance of the classifier (null for mock fixtures). For the trained
    # demonstration SVM this is kind="svm"; its labels are ARTIFICIAL bands.
    model: Optional[ModelDescriptor] = None


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
    """One saved screening session in a patient's history."""

    scan_id: str
    report_id: Optional[str] = None
    test_type: TestType
    status: ScanStatus
    source: Optional[DataSource] = None
    is_simulated: bool = True
    # Null for failed-quality scans — never a fabricated result.
    measurement: Optional[Measurement] = None
    classification: Optional[Classification] = None
    created_at: str


class ScreeningHistoryResponse(BaseModel):
    patient_id: str
    entries: list[ScreeningHistoryEntry]
    disclaimer: str


class ReportPatient(BaseModel):
    """Minimal fictional patient context embedded in a report."""

    patient_id: str
    display_name: Optional[str] = None
    age: int
    sex: Optional[str] = None


class ScreeningReportResponse(BaseModel):
    """GET /api/reports/{id} — a saved session joined with its analysis.

    The report ID is the screening-session ID: reports are a rendered view
    over persisted scan data, not a separate record.
    """

    report_id: str
    scan_id: str
    created_at: str
    patient: ReportPatient
    test: TestMetadata
    analysis: ScanAnalysisResponse
    disclaimer: str


class AssistantQuality(BaseModel):
    passed: bool
    blur_score: Optional[float] = None
    issues: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class AssistantContextResponse(BaseModel):
    """GET /api/reports/{id}/assistant-context — de-identified report summary.

    Grounding data for the "Aarogya AI" assistant. It deliberately contains NO
    patient identifiers (no name, patient ID, report/session ID, age, sex,
    timestamps) and NO image data. NOTE: the app has no authentication; this
    endpoint is no more protected than GET /api/reports/{id} (knowledge of a
    random report ID). Scope: fictional demonstration records only.
    """

    test_type: TestType
    test_name: str
    sample_type: SampleType
    status: ScanStatus
    source: DataSource
    clinically_validated: bool = False
    measurement: Optional[Measurement] = None
    classification: Optional[Classification] = None
    quality: AssistantQuality
    roi_detection: Optional[RoiDetection] = None
    model: ModelDescriptor
    explanation: Explanation
    interpretation_note: str
    disclaimer: str
