"""Inference API (JSON-compatible results, never raises for bad input).

    predict_hemoglobin(image_path, patient_info=None) -> dict
    get_model_info() -> dict

Contract:
    * ``source`` is always ``"synthetic"`` and ``clinically_validated`` is ``False``.
    * On ANY failure (missing/invalid input, unreadable image, no reaction area,
      quality problem, missing or unloadable model, unexpected internal error)
      the result has ``status != "ok"``, ``predicted_hb_g_dl`` and
      ``prediction_interval_g_dl`` are ``None`` and ``failure_reason`` explains
      why. No fabricated numbers.
    * Results never contain absolute local file paths: ``image`` is the file
      name only (or ``"<bytes>"``) and paths inside messages are reduced to
      file names.
    * ``patient_info`` is accepted for interface compatibility and echoed only
      as a list of provided keys; it is NOT used by the model.
    * ``prediction_interval_g_dl`` is an empirical band from out-of-fold
      absolute-error quantiles on synthetic data - not a clinical confidence
      interval.
    * Only the SVR (``models/hb_svr.joblib``) is used. The demo SVM on
      artificial bands is an optional experimental artifact and is never used
      or returned here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from . import DISCLAIMER, __version__
from . import config as C
from .feature_extraction import extract_features, feature_vector
from .preprocessing import preprocess

_MODEL_CACHE: dict = {}

STATUSES = ("ok", "invalid_input", "load_failed", "detection_failed", "quality_failed",
            "feature_extraction_failed", "prediction_failed", "model_unavailable", "internal_error")

LIMITATIONS = (
    "Synthetic data only: trained and tested on generated images from one invented color mapping and one contributor.",
    "Output is a simulated hemoglobin-equivalent value, not a measurement; not clinically validated.",
    "Expects a 512x512 RGB image with one colored rectangle on white paper; real phone photos are untested.",
    "White-paper normalization is not colorimetric calibration (no reference patches).",
    "prediction_interval_g_dl is an empirical synthetic error band, not a clinical confidence interval.",
    "patient_info is not used.",
)


class ModelLoadError(ValueError):
    """Model file exists but cannot be loaded or is not a valid bundle."""


def load_model(path: Path | str = C.SVR_MODEL_FILE) -> dict:
    """Load (and cache) the SVR bundle. Raises FileNotFoundError or ModelLoadError.

    Only load model files produced by this project's training pipeline: joblib
    files are pickles and can execute code when loaded.
    """
    path = Path(path)
    key = str(path.resolve())
    if key not in _MODEL_CACHE:
        if not path.is_file():
            raise FileNotFoundError(f"model file not found: {path.name}")
        try:
            bundle = joblib.load(path)
        except Exception as exc:  # corrupt file, incompatible library versions, missing classes ...
            raise ModelLoadError(f"model file {path.name} could not be loaded ({type(exc).__name__}: {exc})") from exc
        if not isinstance(bundle, Mapping):
            raise ModelLoadError(f"model file {path.name} is not a model bundle (got {type(bundle).__name__})")
        missing = [k for k in ("pipeline", "feature_order", "metadata") if k not in bundle]
        if missing:
            raise ModelLoadError(f"model bundle {path.name} is missing {missing}")
        if not hasattr(bundle["pipeline"], "predict"):
            raise ModelLoadError(f"model bundle {path.name} has no usable 'pipeline'")
        _MODEL_CACHE[key] = bundle
    return _MODEL_CACHE[key]


_ABS_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\)[^\s;,'\"()]+|(?<![\w.])/(?:[^\s/;,'\"()]+/)+[^\s;,'\"()]*")


def _redact(text, paths=()) -> str | None:
    """Replace absolute paths in a message by their file name."""
    if text is None:
        return None
    text = str(text)
    for p in paths:
        if p:
            for form in {str(p), str(Path(p).resolve()) if Path(p).is_absolute() else None}:
                if form and len(form) > 3:
                    text = text.replace(form, Path(form).name)
    return _ABS_PATH_RE.sub(lambda m: os.path.basename(m.group(0).rstrip("\\/")) or "<path>", text)


def _image_ref(image_path) -> str:
    if image_path is None:
        return "<none>"
    if isinstance(image_path, (bytes, bytearray, memoryview)):
        return "<bytes>"
    if isinstance(image_path, (str, os.PathLike)):
        return Path(image_path).name or "<path>"
    return f"<{type(image_path).__name__}>"


def _base_result(image_ref: str, meta: dict | None) -> dict:
    return {
        "status": "error",
        "predicted_hb_g_dl": None,
        "unit": C.TARGET_UNIT,
        "prediction_interval_g_dl": None,
        "interval_basis": None,
        "quality_status": None,
        "quality_issues": [],
        "quality_metrics": {},
        "detection": None,
        "warnings": [],
        "failure_reason": None,
        "model_identifier": (meta or {}).get("model_identifier", C.MODEL_IDENTIFIER),
        "model_version": (meta or {}).get("model_version"),
        "source": "synthetic",
        "clinically_validated": False,
        "disclaimer": DISCLAIMER,
        "image": image_ref,
        "patient_info_keys_received": [],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _fail(res: dict, status: str, reason, paths=()) -> dict:
    """Mark a result as failed: it never carries a value or interval."""
    res.update(status=status, failure_reason=_redact(reason, paths) or status, predicted_hb_g_dl=None,
               prediction_interval_g_dl=None, interval_basis=None)
    return res


def _validate_input(image_path):
    """Return (normalized_input, error). Accepts str/PathLike paths, bytes-like data or uint8 RGB arrays."""
    if image_path is None:
        return None, "no image provided (image_path is None)"
    if isinstance(image_path, memoryview):
        image_path = image_path.tobytes()
    if isinstance(image_path, (bytes, bytearray)):
        return image_path, None  # empty bytes keep their previous behaviour: load_failed from the loader
    if isinstance(image_path, (str, os.PathLike)):
        return (image_path, None) if str(image_path).strip() else (None, "empty image path")
    if isinstance(image_path, np.ndarray):
        return image_path, None
    return None, f"unsupported image input type {type(image_path).__name__}; expected a file path or image bytes"


def predict_hemoglobin(image_path, patient_info: dict | None = None, model_path: Path | str = C.SVR_MODEL_FILE,
                       expected_size: tuple[int, int] | None = C.EXPECTED_SIZE) -> dict:
    """Predict the SIMULATED hemoglobin-equivalent value for one image.

    ``image_path`` may be a file path (str / Path) or encoded image bytes
    (PNG/JPEG/...). Never raises for bad input or a broken model: every problem
    is returned as ``status != "ok"`` with ``predicted_hb_g_dl = None``.
    """
    paths = (image_path, model_path) if isinstance(image_path, (str, os.PathLike)) else (model_path,)
    res = _base_result(_image_ref(image_path), None)
    try:
        try:
            bundle = load_model(model_path)
        except (FileNotFoundError, ModelLoadError, OSError) as exc:
            return _fail(res, "model_unavailable", exc, paths)
        meta = bundle["metadata"]
        res.update(model_identifier=meta.get("model_identifier", C.MODEL_IDENTIFIER),
                   model_version=meta.get("model_version"))
        if patient_info:
            if isinstance(patient_info, Mapping):
                res["patient_info_keys_received"] = sorted(map(str, patient_info))
                res["warnings"].append("patient_info is not used by this synthetic model")
            else:
                res["warnings"].append(f"patient_info ignored: expected a dict, got {type(patient_info).__name__}")

        image, err = _validate_input(image_path)
        if err:
            return _fail(res, "invalid_input", err, paths)

        pre = preprocess(image, expected_size)
        res["quality_status"] = pre.status
        res["quality_issues"] = [_redact(i, paths) for i in pre.issues]
        res["quality_metrics"] = dict(pre.quality)
        if pre.detection is not None and pre.detection.ok:
            res["detection"] = {"method": pre.detection.method, "confidence": pre.detection.confidence,
                                "corners_xy": np.round(pre.detection.corners, 1).tolist()}
        if not pre.ok:
            return _fail(res, pre.status, "; ".join(pre.issues) or pre.status, paths)

        try:
            feats = extract_features(pre)
            x = feature_vector(feats, bundle["feature_order"])
        except (ValueError, KeyError) as exc:
            return _fail(res, "feature_extraction_failed", exc, paths)
        try:
            y = float(np.asarray(bundle["pipeline"].predict(x)).ravel()[0])
        except Exception as exc:  # e.g. estimator pickled with an incompatible library version
            return _fail(res, "prediction_failed", f"model prediction failed ({type(exc).__name__}: {exc})", paths)
        if not np.isfinite(y):
            return _fail(res, "prediction_failed", "model produced a non-finite value", paths)

        lo_t, hi_t = meta["training_target_range"]
        out_feats = [c for c, (lo, hi) in meta["feature_ranges_train"].items()
                     if not (lo - 0.1 * (hi - lo) <= feats[c] <= hi + 0.1 * (hi - lo))]
        if out_feats:
            res["warnings"].append(f"input outside training feature range for {len(out_feats)} feature(s): "
                                   f"{out_feats[:5]} - prediction is an extrapolation")
        if y < lo_t or y > hi_t:
            res["warnings"].append(f"prediction {y:.2f} outside training target range [{lo_t}, {hi_t}]")
        band = meta["oof_abs_error_quantiles"]["p90"]
        res.update(status="ok", predicted_hb_g_dl=round(y, 2),
                   prediction_interval_g_dl=[round(y - band, 2), round(y + band, 2)],
                   interval_basis="+/- 90th percentile of out-of-fold absolute error on SYNTHETIC train+val data")
        return res
    except Exception as exc:  # last-resort guard: never raise, never return a value
        return _fail(res, "internal_error", f"unexpected {type(exc).__name__}: {exc}", paths)


_FILE_HASH_CACHE: dict = {}


def _sha256(path: Path) -> str:
    key = (str(path.resolve()), path.stat().st_mtime_ns)
    if key not in _FILE_HASH_CACHE:
        _FILE_HASH_CACHE[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _FILE_HASH_CACHE[key]


def get_model_info(model_path: Path | str = C.SVR_MODEL_FILE) -> dict:
    """Model metadata for health / info endpoints. Loads (and caches) the model; runs no prediction.

    Returns ``status == "ok"`` with metadata, or ``status == "model_unavailable"``
    with ``failure_reason``. Never raises; contains no absolute paths.
    """
    model_path = Path(model_path)
    info = {"status": "model_unavailable", "failure_reason": None, "model_identifier": C.MODEL_IDENTIFIER,
            "model_version": None, "package_version": __version__, "model_file": model_path.name,
            "source": "synthetic", "clinically_validated": False, "disclaimer": DISCLAIMER,
            "limitations": list(LIMITATIONS)}
    try:
        meta = load_model(model_path)["metadata"]
    except Exception as exc:
        info["failure_reason"] = _redact(exc, (model_path,))
        return info
    try:
        import cv2
        import sklearn

        trained = meta.get("environment", {})
        runtime = {"python": platform.python_version(), "sklearn": sklearn.__version__, "numpy": np.__version__,
                   "opencv": cv2.__version__, "joblib": joblib.__version__}
        warnings = [f"{lib} {runtime[lib]} differs from training version {trained[lib]}; predictions may differ"
                    for lib in ("sklearn", "numpy") if lib in trained and trained[lib] != runtime[lib]]
        ds = meta.get("dataset", {})
        svm_file = model_path.parent / C.SVM_MODEL_FILE.name
        info.update({
            "status": "ok",
            "model_identifier": meta.get("model_identifier", C.MODEL_IDENTIFIER),
            "model_version": meta.get("model_version"),
            "model_sha256": _sha256(model_path),
            "created_utc": meta.get("created_utc"),
            "estimator": meta.get("estimator"),
            "hyperparameters": meta.get("hyperparameters"),
            "target": meta.get("target"),
            "unit": meta.get("unit"),
            "feature_set": meta.get("feature_set"),
            "n_features": len(meta.get("feature_order", [])),
            "feature_order": list(meta.get("feature_order", [])),
            "training_target_range": meta.get("training_target_range"),
            "prediction_interval_half_width_g_dl": meta.get("oof_abs_error_quantiles", {}).get("p90"),
            "validation_metrics": meta.get("validation_metrics"),
            "test_metrics": meta.get("test_metrics"),
            "dataset": {k: ds.get(k) for k in ("fingerprint", "sources", "n_train", "n_val", "n_test",
                                               "n_excluded_preprocessing_failed", "split_seed")},
            "input_contract": {"accepted_inputs": ["file path (str or pathlib.Path)", "encoded image bytes"],
                               "image_formats_verified": ["PNG", "JPEG", "WEBP", "BMP"],
                               "expected_size_px": list(C.EXPECTED_SIZE), "channels": 3,
                               "patient_info_used": False},
            "statuses": list(STATUSES),
            "training_environment": trained,
            "runtime_environment": runtime,
            "warnings": warnings,
            "experimental_artifacts": {"demo_svm": {
                "file": svm_file.name, "present": svm_file.is_file(), "used_by_inference": False,
                "note": "experimental only; trained on artificial equal-width bands with no clinical meaning"}},
        })
    except Exception as exc:
        info.update(status="model_unavailable",
                    failure_reason=_redact(f"metadata error {type(exc).__name__}: {exc}", (model_path,)))
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description="Predict the SIMULATED hemoglobin value for image(s).")
    ap.add_argument("images", nargs="*")
    ap.add_argument("--model", default=str(C.SVR_MODEL_FILE))
    ap.add_argument("--info", action="store_true", help="print model info (get_model_info) and exit")
    a = ap.parse_args(argv)
    if a.info or not a.images:
        print(json.dumps(get_model_info(a.model), indent=2))
        return
    out = [predict_hemoglobin(p, model_path=a.model) for p in a.images]
    print(json.dumps(out if len(out) > 1 else out[0], indent=2))


if __name__ == "__main__":
    main()
