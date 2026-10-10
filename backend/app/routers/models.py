"""GET /api/models/info — transparency about the current inference stack."""

from fastapi import APIRouter

from ..config import SIMULATION_DISCLAIMER
from ..schemas import ModelDescriptor, ModelsInfoResponse
from ..services import inference, ml_hemoglobin

router = APIRouter(tags=["models"])


@router.get("/models/info", response_model=ModelsInfoResponse)
def get_models_info() -> ModelsInfoResponse:
    available, reason = inference.ml_status()
    svm_available, svm_reason = inference.svm_status()
    active: list[ModelDescriptor] = []
    if available:
        active.append(ml_hemoglobin.model_descriptor())
    if svm_available:
        svm_model = ml_hemoglobin.svm_descriptor()
        if svm_model:
            active.append(svm_model)
    active.append(inference.MOCK_MODEL)

    notes = (
        "Hemoglobin uses a trained SVR model (OpenCV preprocessing + color "
        "features) evaluated only on synthetic images; its output is a "
        "simulated hemoglobin-equivalent value. A demonstration SVM assigns an "
        "ARTIFICIAL category (equal-width bands of the synthetic value range, "
        "no clinical meaning, not a severity assessment). Glucose and urine "
        "albumin still use deterministic mock fixtures. Nothing is "
        "clinically validated."
    )
    if not available:
        notes = (
            f"The hemoglobin ML model is UNAVAILABLE ({reason}); hemoglobin "
            "scans return HTTP 503 and are never mocked. " + notes
        )
    elif not svm_available:
        notes = (
            f"The demonstration SVM is UNAVAILABLE ({svm_reason}); hemoglobin "
            "scans still return the SVR estimate with classification null "
            "(a category is never invented). " + notes
        )

    return ModelsInfoResponse(
        inference_mode=inference.INFERENCE_MODE,
        clinically_validated=False,
        active_models=active,
        planned_pipeline=[
            "opencv: reaction-area detection, quality gate, white-paper "
            "normalization, color features (hemoglobin: active)",
            "svr: simulated hemoglobin-equivalent estimation, scikit-learn "
            "(hemoglobin: active)",
            "svm: demonstration classifier on ARTIFICIAL equal-width bands "
            "(hemoglobin: active; no clinical meaning)",
        ],
        notes=notes,
        disclaimer=SIMULATION_DISCLAIMER,
        test_inference=inference.test_backends(),
        test_classification=inference.test_classifiers(),
    )
