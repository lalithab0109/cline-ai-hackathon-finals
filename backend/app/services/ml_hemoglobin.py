"""Adapter around the standalone hemoglobin ML package (`ml/aarogya-bindu-ml`).

This module only *wraps* the ML project's public API
(`aarogya_hb_ml.inference.predict_hemoglobin` / `get_model_info`); it does not
re-implement any OpenCV preprocessing or feature extraction. It converts the
ML result dict into the stable `ScanAnalysisResponse` contract.

Behavioural guarantees:
- The model is imported and loaded once, then cached (the ML package keeps its
  own bundle cache keyed by the resolved model path).
- Paths come from `config` (resolved from this file, never the CWD).
- If the package, its dependencies or the model file are unavailable we raise
  `MLUnavailableError` - the caller returns HTTP 503. We NEVER fall back to
  mock values for hemoglobin.
- Failed scans carry `measurement = None` and `classification = None`.
- Classification comes from the saved DEMONSTRATION SVM, whose labels are
  ARTIFICIAL equal-width bands of the synthetic target range with no clinical
  meaning. The SVM consumes the 30 SVR features PLUS the raw SVR output
  (`svr_pred`), in the exact order stored in its bundle. It is optional: if it
  is missing/invalid/fails, the SVR estimate is still returned with
  `classification = None` and a warning - a class is never invented.
- The SVR value/interval/quality come from `predict_hemoglobin` unchanged.
- Every value is a plain JSON type (float/str/bool/list/dict).
"""

from __future__ import annotations

import logging
import math
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from ..config import (
    ML_HEMOGLOBIN_MODEL_PATH,
    ML_HEMOGLOBIN_SVM_MODEL_PATH,
    ML_PROJECT_DIR,
    REPO_ROOT,
    SIMULATION_DISCLAIMER,
)
from ..schemas import (
    Classification,
    DataSource,
    Explanation,
    ImageAnalysis,
    Measurement,
    ModelDescriptor,
    QualityResult,
    RoiDetection,
    ScanAnalysisResponse,
    ScanStatus,
    TestType,
)

logger = logging.getLogger("aarogya.ml")

# ML result statuses that mean "this image could not be used" (patient can retry).
_IMAGE_FAILURE_STATUSES = frozenset(
    {
        "invalid_input",
        "load_failed",
        "detection_failed",
        "quality_failed",
        "feature_extraction_failed",
    }
)
# ML result statuses that mean the pipeline itself failed on this input.
_PROCESSING_FAILURE_STATUSES = frozenset({"prediction_failed", "internal_error"})

# Plain-language guidance for the ML quality-gate issue codes. The raw
# technical issue is always appended so nothing is hidden.
_ISSUE_GUIDANCE: tuple[tuple[str, str], ...] = (
    (
        "invalid_image",
        "The image could not be read by the hemoglobin demonstration model. "
        "It accepts only 8-bit, 3-channel 512x512 strip images.",
    ),
    (
        "no plausible reaction rectangle",
        "No reaction area (a colored rectangle on white paper) was found in "
        "the image. Make sure the whole strip is visible and well lit.",
    ),
    (
        "low_detection_confidence",
        "The reaction area could not be located with enough confidence. "
        "Retake the photo with the strip flat, fully visible, on white paper.",
    ),
    (
        "overexposed_or_clipped_roi",
        "The reaction area is overexposed or clipped. Retake the photo in "
        "softer, even lighting without glare.",
    ),
    (
        "background_too_dark_for_white_normalization",
        "The white paper background is too dark to normalize the colors. "
        "Retake the photo in brighter, even light.",
    ),
    (
        "too_blurry",
        "The photo is too blurry. Hold the camera steady and retake it.",
    ),
    (
        "roi_too_small",
        "The reaction area is too small in the image. Move closer and retake.",
    ),
    (
        "roi_not_uniform",
        "The reaction area is not uniformly colored (possible glare, shadow "
        "or stain). Retake the photo in even lighting.",
    ),
)


class MLUnavailableError(RuntimeError):
    """The hemoglobin ML pipeline cannot run (missing package/deps/model)."""


_lock = threading.Lock()
_module: Any = None  # aarogya_hb_ml.inference, once imported
_info: Optional[dict] = None  # get_model_info() result of the loaded model
# Demonstration SVM (optional). `_svm` is None when it is unavailable, in which
# case `_svm_error` says why. Never mocked, never defaulted.
_svm: Optional[dict] = None
_svm_error: Optional[str] = None

_ABS_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/)(?:[^\s'\"()]+[\\/])+[^\s'\"()]*")


def _redact(text: object) -> str:
    """Reduce absolute paths inside a message to their file names."""
    return _ABS_PATH.sub(lambda m: os.path.basename(m.group(0).rstrip("/\\")), str(text))


def _display(path: Path) -> str:
    """Repo-relative path for messages (avoid leaking absolute paths)."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return path.name


def _import_ml_module() -> Any:
    src_dir = ML_PROJECT_DIR / "src"
    if not (src_dir / "aarogya_hb_ml" / "inference.py").is_file():
        raise MLUnavailableError(
            "Hemoglobin ML package not found at "
            f"'{_display(src_dir)}/aarogya_hb_ml'. Check ML_PROJECT_DIR."
        )
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    try:
        import aarogya_hb_ml.inference as module  # type: ignore[import-not-found]
    except ImportError as exc:
        raise MLUnavailableError(
            f"Hemoglobin ML dependencies are missing ({exc}). Install "
            "ml/aarogya-bindu-ml/requirements-inference.txt into the backend "
            "environment (pip install -r backend/requirements.txt)."
        ) from exc
    return module


def load() -> dict:
    """Import the ML package and load the SVR once; return its model info.

    Idempotent and thread-safe. Raises MLUnavailableError with an actionable,
    path-free message when anything is missing or incompatible.
    """
    global _module, _info
    if _info is not None:
        return _info
    with _lock:
        if _info is not None:
            return _info
        if not ML_HEMOGLOBIN_MODEL_PATH.is_file():
            raise MLUnavailableError(
                "Hemoglobin model artifact not found at "
                f"'{_display(ML_HEMOGLOBIN_MODEL_PATH)}'."
            )
        module = _import_ml_module()
        info = module.get_model_info(ML_HEMOGLOBIN_MODEL_PATH)
        if info.get("status") != "ok":
            raise MLUnavailableError(
                "Hemoglobin model could not be loaded: "
                f"{info.get('failure_reason') or 'unknown error'}"
            )
        for warning in info.get("warnings") or []:
            logger.warning("hemoglobin model: %s", warning)
        _module = module
        # The SVM is optional: a failure here must NOT take down the SVR.
        _load_svm(module)
        _info = info
        logger.info(
            "Loaded %s v%s (sha256 %s...)",
            info.get("model_identifier"),
            info.get("model_version"),
            str(info.get("model_sha256"))[:12],
        )
        return _info


SVM_FEATURE_EXTRA = "svr_pred"
SVM_METHOD = "svm_synthetic_demo"


def _load_svm(module: Any) -> None:
    """Load + strictly validate the demonstration SVM (never raises).

    Validation (any failure => classification disabled, SVR unaffected):
    - file exists and loads through the ML package's own `load_model`;
    - input features == SVR feature_order + ["svr_pred"], same order;
    - classes_ == [0, 1, 2] and there is one band name per class;
    - metadata says synthetic / not clinically validated, bands are artificial;
    - the SVM was trained against THIS SVR (created_utc matches).
    """
    global _svm, _svm_error
    _svm, _svm_error = None, None
    path = ML_HEMOGLOBIN_SVM_MODEL_PATH
    try:
        if not path.is_file():
            raise ValueError(f"demonstration SVM artifact not found at '{_display(path)}'")
        bundle = module.load_model(path)
        svr_bundle = module.load_model(ML_HEMOGLOBIN_MODEL_PATH)
        meta = bundle["metadata"]
        order = list(bundle["feature_order"])
        expected = list(svr_bundle["feature_order"]) + [SVM_FEATURE_EXTRA]
        if order != expected:
            raise ValueError("SVM feature order does not match SVR features + svr_pred")
        if list(meta.get("input_features", [])) != order:
            raise ValueError("SVM bundle feature order differs from its metadata")
        names = list(meta.get("band_names", []))
        classes = [int(c) for c in bundle["pipeline"].steps[-1][1].classes_]
        if classes != list(range(len(names))) or not names:
            raise ValueError("SVM classes do not match its band names")
        if meta.get("source") != "synthetic" or meta.get("clinically_validated") is not False:
            raise ValueError("SVM metadata is not marked synthetic / not clinically validated")
        if not all("artificial" in n for n in names):
            raise ValueError("SVM band names are not marked artificial")
        dep = (meta.get("svr_dependency") or {}).get("svr_created_utc")
        if dep != svr_bundle["metadata"].get("created_utc"):
            raise ValueError("SVM was trained against a different SVR")
        _svm = {
            "pipeline": bundle["pipeline"],
            "order": order,
            "names": names,
            "meta": meta,
            "descriptor": ModelDescriptor(
                identifier=str(meta["model_identifier"]),
                version=str(meta["model_version"]),
                kind="svm",
            ),
        }
        logger.info("Loaded demonstration SVM %s v%s", meta["model_identifier"], meta["model_version"])
    except Exception as exc:  # noqa: BLE001 - optional component, report and continue
        _svm_error = _redact(f"{type(exc).__name__}: {exc}")
        logger.warning("Demonstration SVM unavailable (classification disabled): %s", _svm_error)


def svm_status() -> tuple[bool, Optional[str]]:
    """(demonstration SVM available, reason if not). Requires the SVR to load."""
    load()
    return (_svm is not None), _svm_error


def svm_descriptor() -> Optional[ModelDescriptor]:
    load()
    return _svm["descriptor"] if _svm else None


def is_available() -> tuple[bool, Optional[str]]:
    """(available, reason_if_not) without raising - for status endpoints."""
    try:
        load()
        return True, None
    except MLUnavailableError as exc:
        return False, str(exc)


def model_descriptor() -> ModelDescriptor:
    info = load()
    return ModelDescriptor(
        identifier=str(info["model_identifier"]),
        version=str(info["model_version"]),
        kind="svr",
    )


def _num(value: Any) -> Optional[float]:
    """JSON-safe float (no NaN/inf, no numpy scalars)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _issue_messages(result: dict) -> list[str]:
    """Patient-facing quality issues: guidance first, raw ML code second."""
    raw = [str(i) for i in (result.get("quality_issues") or [])]
    if not raw and result.get("failure_reason"):
        raw = [str(result["failure_reason"])]
    messages: list[str] = []
    for item in raw:
        guidance = next(
            (text for key, text in _ISSUE_GUIDANCE if key in item), None
        )
        messages.append(f"{guidance} (detail: {item})" if guidance else item)
    return messages or ["The image could not be processed."]


def _quality(result: dict, passed: bool) -> QualityResult:
    metrics = result.get("quality_metrics") or {}
    clean_metrics = {
        key: number
        for key, value in metrics.items()
        if (number := _num(value)) is not None
    }
    return QualityResult(
        passed=passed,
        blur_score=_num(metrics.get("sharpness_laplacian_var")),
        # The pipeline normalizes by white paper; there are no reference
        # patches, so calibration does not apply (null, not "failed"). This
        # limitation is stated in the explanation.
        calibration_detected=None,
        calibration_error=None,
        issues=[] if passed else _issue_messages(result),
        metrics=clean_metrics,
    )


def _roi(result: dict) -> Optional[RoiDetection]:
    det = result.get("detection")
    if not det:
        return None
    return RoiDetection(
        method=str(det.get("method", "")),
        confidence=_num(det.get("confidence")) or 0.0,
        corners_xy=[
            [round(float(x), 1), round(float(y), 1)]
            for x, y in (det.get("corners_xy") or [])
        ],
    )


_LIMITATIONS = [
    "Trained and evaluated only on synthetic images generated from one invented color mapping; not clinically validated.",
    "The value is a simulated hemoglobin-equivalent, not a hemoglobin measurement, and cannot diagnose or rule out any condition.",
    "Expects a 512x512 image with one colored rectangle on white paper; real phone photos are untested.",
    "White-paper normalization is not colorimetric calibration (no reference patches).",
    "The interval is an empirical synthetic error band, not a clinical confidence interval.",
]

# Added when a demonstration category is present / absent on a successful scan.
_LIMITATION_CATEGORY = (
    "The category is an artificial label from a demonstration SVM trained on "
    "equal-width bands of the synthetic value range; it has no clinical "
    "meaning and is not a severity assessment."
)
_LIMITATION_NO_CATEGORY = (
    "No category is assigned to this scan: the demonstration classifier was "
    "not available, and a category is never invented."
)


def _classify(image_bytes: bytes, reported_value: float) -> tuple[Optional[Classification], Optional[str]]:
    """Run the demonstration SVM; returns (classification, warning).

    Contract (from the saved SVM bundle): input = the SVR's 30 features, in
    order, PLUS `svr_pred` (the SVR's raw, unrounded output). The scaler is
    part of the SVM pipeline. Predicted class index -> `band_names[index]`.

    The ML package exposes no public SVM function and `predict_hemoglobin`
    does not return its features, so the features are recomputed ONCE with the
    package's own public preprocess/extract_features/feature_vector (one extra
    ~tens-of-ms pass, only for successful scans). Guards: the recomputed SVR
    output must equal the value `predict_hemoglobin` reported, otherwise NO
    class is returned. Any failure -> (None, warning); a class is never invented.
    """
    if _svm is None:
        return None, (
            "Demonstration category unavailable (the demonstration SVM could not "
            f"be loaded: {_svm_error}). The SVR estimate is unaffected."
        )
    try:
        import numpy as np

        svr_bundle = _module.load_model(ML_HEMOGLOBIN_MODEL_PATH)
        pre = _module.preprocess(image_bytes)
        if not pre.ok:
            raise ValueError(f"preprocessing did not pass on re-check ({pre.status})")
        feats = _module.extract_features(pre)
        x_svr = _module.feature_vector(feats, list(svr_bundle["feature_order"]))
        raw = float(np.asarray(svr_bundle["pipeline"].predict(x_svr)).ravel()[0])
        if not math.isfinite(raw) or round(raw, 2) != round(reported_value, 2):
            raise ValueError("recomputed SVR output differs from the reported estimate")
        feats = dict(feats, **{SVM_FEATURE_EXTRA: raw})
        x_svm = _module.feature_vector(feats, _svm["order"])  # exact SVM order
        index = int(np.asarray(_svm["pipeline"].predict(x_svm)).ravel()[0])
        names = _svm["names"]
        if not 0 <= index < len(names):
            raise ValueError(f"SVM returned an unknown class index {index}")
    except Exception as exc:  # noqa: BLE001 - classification is best-effort
        reason = _redact(f"{type(exc).__name__}: {exc}")
        logger.warning("SVM classification failed: %s", reason)
        return None, (
            f"Demonstration category unavailable ({reason}). The SVR estimate is unaffected."
        )
    return (
        Classification(
            label=names[index],  # exact label from the saved metadata
            method=SVM_METHOD,
            is_simulated=True,
            model=_svm["descriptor"],
        ),
        None,
    )


def analyze(*, image_bytes: bytes, scan_id: str) -> ScanAnalysisResponse:
    """Run the trained SVR (+ demonstration SVM) on the image and map it to the API contract.

    Raises MLUnavailableError if the SVR cannot be loaded (never mocks).
    """
    info = load()  # raises MLUnavailableError; cached after first success
    model = model_descriptor()

    # `predict_hemoglobin` never raises; every failure is a status != "ok".
    # patient_info is intentionally not passed: the model does not use it.
    result: dict = _module.predict_hemoglobin(
        image_bytes, model_path=ML_HEMOGLOBIN_MODEL_PATH
    )
    value = _num(result.get("predicted_hb_g_dl"))

    if result.get("status") == "ok" and value is not None:
        classification, class_warning = _classify(image_bytes, value)
        return _success(result, value, info, model, scan_id, classification, class_warning)
    return _failure(result, model, scan_id)


_ARTIFICIAL_NOTE = (
    "The category is a demonstration label from an SVM trained on ARTIFICIAL, "
    "equal-width bands of the synthetic value range (4.0-8.7, 8.7-13.3, "
    "13.3-18.0). Artificial category based on synthetic training labels. "
    "Not a medical severity assessment."
)


def _success(
    result: dict,
    value: float,
    info: dict,
    model: ModelDescriptor,
    scan_id: str,
    classification: Optional[Classification] = None,
    class_warning: Optional[str] = None,
) -> ScanAnalysisResponse:
    interval = result.get("prediction_interval_g_dl") or []
    warnings = [str(w) for w in (result.get("warnings") or [])]
    summary = (
        f"A trained SVR model estimated a simulated hemoglobin-equivalent value "
        f"of {value:.2f} g/dL from the reaction area of your image. This is a "
        "demonstration on synthetic data; it is not a hemoglobin measurement "
        "or a medical diagnosis."
    )
    if len(interval) == 2:
        summary += (
            f" Synthetic error band: {interval[0]:.2f}-{interval[1]:.2f} g/dL "
            "(an empirical band from synthetic data, not a clinical confidence "
            "interval)."
        )
    mae = (info.get("test_metrics") or {}).get("mae")

    inputs_used = [
        "reaction-area color features (30, white-paper normalized) "
        "from the uploaded image"
    ]
    limitations = list(_LIMITATIONS)
    extra_warnings: list[str] = []
    if classification is not None:
        summary += " " + _ARTIFICIAL_NOTE
        inputs_used.append(
            "the SVR's simulated value (used, with the same 30 features, by "
            "the demonstration SVM)"
        )
        limitations.append(_LIMITATION_CATEGORY)
        svm_mae = (_svm or {}).get("meta", {}).get("test_metrics", {}).get("balanced_accuracy")
        extra_warnings.append(
            "The category's synthetic test balanced accuracy "
            f"({svm_mae}) only measures agreement with artificial bands; "
            "it says nothing about real patients."
        )
    else:
        limitations.append(_LIMITATION_NO_CATEGORY)
        if class_warning:
            extra_warnings.append(class_warning)

    return ScanAnalysisResponse(
        scan_id=scan_id,
        report_id=None,
        test_type=TestType.HEMOGLOBIN,
        status=ScanStatus.SUCCESS,
        source=DataSource.SYNTHETIC,
        clinically_validated=False,
        model=model,
        quality=_quality(result, passed=True),
        image_analysis=ImageAnalysis(roi_detection=_roi(result)),
        measurement=Measurement(
            value=round(value, 2),
            unit=str(result.get("unit") or "g/dL"),
            method="svr_rbf_synthetic",
            is_simulated=True,
        ),
        classification=classification,
        explanation=Explanation(
            summary=summary,
            inputs_used=inputs_used,
            limitations=limitations,
            warnings=warnings
            + [
                "Patient age and sex were not used by these models.",
                f"Synthetic test-set MAE {mae} g/dL measures agreement with "
                "an invented color mapping only.",
            ]
            + extra_warnings,
        ),
        disclaimer=SIMULATION_DISCLAIMER,
    )


def _failure(
    result: dict, model: ModelDescriptor, scan_id: str
) -> ScanAnalysisResponse:
    """Failed scan: null measurement/classification, never a fabricated value.

    Image problems (unreadable image, no reaction area, quality gate) are
    `quality_failed` (patient can retake). Pipeline/processing errors and any
    undocumented status are `error`.
    """
    status = str(result.get("status"))
    if status in _IMAGE_FAILURE_STATUSES:
        scan_status = ScanStatus.QUALITY_FAILED
        issues = _issue_messages(result)
        summary = (
            "The image did not pass the hemoglobin model's checks, so no "
            "screening result was generated. Please retake the photo and try "
            "again."
        )
    else:
        scan_status = ScanStatus.ERROR
        issues = [
            "The hemoglobin demonstration model could not process this image "
            f"(status: {status}). Please try again with a different photo."
        ]
        summary = (
            "The analysis could not be completed because of a processing "
            "error, so no screening result was generated."
        )

    detail = str(result.get("failure_reason") or status)
    quality = _quality(result, passed=False).model_copy(update={"issues": issues})
    return ScanAnalysisResponse(
        scan_id=scan_id,
        report_id=None,
        test_type=TestType.HEMOGLOBIN,
        status=scan_status,
        source=DataSource.SYNTHETIC,
        clinically_validated=False,
        model=model,
        quality=quality,
        image_analysis=(
            ImageAnalysis(roi_detection=_roi(result))
            if result.get("detection")
            else None
        ),
        measurement=None,
        classification=None,
        explanation=Explanation(
            summary=summary,
            inputs_used=[],
            limitations=list(_LIMITATIONS),
            warnings=[
                "No measurement or classification was produced for this scan.",
                f"Pipeline status: {status} ({detail}).",
            ],
        ),
        disclaimer=SIMULATION_DISCLAIMER,
    )
