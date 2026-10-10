"""GET /api/models/info — transparency about the current inference stack."""

from fastapi import APIRouter

from ..config import SIMULATION_DISCLAIMER
from ..schemas import ModelDescriptor, ModelsInfoResponse
from ..services.inference import INFERENCE_MODE, MOCK_MODEL

router = APIRouter(tags=["models"])


@router.get("/models/info", response_model=ModelsInfoResponse)
def get_models_info() -> ModelsInfoResponse:
    return ModelsInfoResponse(
        inference_mode=INFERENCE_MODE,
        clinically_validated=False,
        active_models=[MOCK_MODEL],
        planned_pipeline=[
            "opencv: strip/pad detection, quality checks, color calibration",
            "svr: experimental synthetic biomarker estimation (scikit-learn)",
            "svm: illustrative screening severity classification (scikit-learn)",
        ],
        notes=(
            "The application currently uses deterministic mock inference. "
            "Real OpenCV -> SVR -> SVM models are developed independently "
            "and will replace the mock adapter without changing the API "
            "contract."
        ),
        disclaimer=SIMULATION_DISCLAIMER,
    )
