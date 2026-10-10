"""Inference boundary between the API and the (future) ML pipeline.

This module is the single seam where mock inference will be replaced by the
real OpenCV -> SVR -> SVM pipeline developed in the `ml/` package. The API
contract (`schemas.ScanAnalysisResponse`) stays identical either way, so no
frontend change will be required.

Planned real implementation (roadmap section 8.4):

    def analyze_strip(image, test_type, patient_info):
        # 1. Validate and inspect image
        # 2. Detect strip, calibrate, extract features (OpenCV)
        # 3. Reject poor-quality scans (quality gate)
        # 4. Run experimental SVR estimate (scikit-learn)
        # 5. Run experimental SVM classification (scikit-learn)
        # 6. Return versioned, explainable structured result

The mock implementation itself is scheduled for the next iteration; this
module currently exposes only the mode flag and model provenance constants
used by the metadata endpoints.
"""

from __future__ import annotations

from ..schemas import ModelDescriptor

# "mock" until the ML pipeline in `ml/` is integrated behind this adapter.
INFERENCE_MODE = "mock"

# Provenance descriptor reported in every (future) analysis response.
MOCK_MODEL = ModelDescriptor(
    identifier="aarogya-bindu-mock-inference",
    version="0.1.0",
    kind="mock",
)


def analyze_strip(*args: object, **kwargs: object) -> None:
    """Placeholder for the unified inference interface.

    Scheduled for the next iteration (deterministic mock first, real ML
    adapter later). Intentionally unimplemented in this iteration.
    """

    raise NotImplementedError(
        "Scan analysis is scheduled for a later iteration. "
        "See Aarogya_Bindu_Development_and_ML_Roadmap.md sections 6 and 8.4."
    )
