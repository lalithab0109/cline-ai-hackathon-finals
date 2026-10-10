import json

import joblib
import numpy as np
import pandas as pd
import pytest
from conftest import make_strip, save_rgb

from aarogya_hb_ml import config as C
from aarogya_hb_ml.inference import predict_hemoglobin
from aarogya_hb_ml.metrics import regression_metrics
from aarogya_hb_ml.train_svm import BAND_NAMES, to_band

needs_model = pytest.mark.skipif(not C.SVR_MODEL_FILE.is_file(), reason="model not trained")
REQUIRED_KEYS = {"status", "predicted_hb_g_dl", "unit", "prediction_interval_g_dl", "quality_status", "quality_issues",
                 "failure_reason", "model_identifier", "model_version", "source", "clinically_validated",
                 "disclaimer", "timestamp_utc", "warnings"}


def test_regression_metrics_known_values():
    m = regression_metrics([1, 2, 3], [1, 2, 5])
    assert m["mae"] == pytest.approx(2 / 3, abs=1e-4) and m["max_abs_error"] == 2 and m["bias"] > 0


def test_artificial_bands():
    assert list(to_band([4.0, 8.6, 8.7, 13.4, 18.0])) == [0, 0, 1, 2, 2]
    assert all("artificial" in b for b in BAND_NAMES)


def test_missing_model_returns_structured_failure(tmp_path, strip_png):
    r = predict_hemoglobin(strip_png, model_path=tmp_path / "nope.joblib")
    assert r["status"] == "model_unavailable" and r["predicted_hb_g_dl"] is None
    assert r["source"] == "synthetic" and r["clinically_validated"] is False


@needs_model
def test_saved_bundle_metadata_consistent():
    b = joblib.load(C.SVR_MODEL_FILE)
    meta = b["metadata"]
    assert b["feature_order"] == meta["feature_order"]
    assert meta["clinically_validated"] is False and meta["source"] == "synthetic"
    for k in ("hyperparameters", "test_metrics", "validation_metrics", "created_utc", "dataset"):
        assert k in meta
    disk = json.loads(C.SVR_META_FILE.read_text())
    assert disk["test_metrics"] == meta["test_metrics"]


@needs_model
def test_predict_on_real_dataset_image_matches_training_pipeline():
    feats = pd.read_csv(C.FEATURES_CSV)
    idx = pd.read_csv(C.DATASET_CSV)
    preds = pd.read_csv(C.PROCESSED_DIR / "svr_test_predictions.csv")
    uid = preds["uid"].iloc[0]
    path = idx.loc[idx["uid"] == uid, "abs_path"].iloc[0]
    r = predict_hemoglobin(path, patient_info={"age": 30})
    assert REQUIRED_KEYS <= set(r)
    assert r["status"] == "ok"
    assert r["predicted_hb_g_dl"] == pytest.approx(preds["svr_pred"].iloc[0], abs=0.006)
    lo, hi = r["prediction_interval_g_dl"]
    assert lo < r["predicted_hb_g_dl"] < hi
    assert r["patient_info_keys_received"] == ["age"]
    json.dumps(r)  # JSON-compatible
    assert feats is not None


@needs_model
@pytest.mark.parametrize("kind", ["blank", "corrupt", "wrong_size", "blurred"])
def test_failures_return_null_measurement(tmp_path, kind):
    if kind == "blank":
        p = save_rgb(tmp_path / "b.png", np.full((512, 512, 3), 240, np.uint8))
    elif kind == "corrupt":
        p = tmp_path / "c.png"
        p.write_bytes(b"\x89PNG\r\n garbage")
    elif kind == "wrong_size":
        p = save_rgb(tmp_path / "w.png", make_strip(size=256, center=(128, 128), wh=(80, 60))[0])
    else:
        p = save_rgb(tmp_path / "bl.png", make_strip(blur=25)[0])
    r = predict_hemoglobin(p)
    assert r["status"] != "ok" and r["predicted_hb_g_dl"] is None and r["prediction_interval_g_dl"] is None
    assert r["failure_reason"]
    json.dumps(r)


@needs_model
def test_prediction_is_monotonic_in_color_intensity():
    """Darker/redder simulated spots should give higher simulated values (mapping direction)."""
    from aarogya_hb_ml.preprocessing import preprocess  # noqa: F401
    idx = pd.read_csv(C.DATASET_CSV)
    clean = idx[idx["augmentation_profile"] == "clean"].sort_values(C.TARGET)
    lo_p, hi_p = clean["abs_path"].iloc[2], clean["abs_path"].iloc[-3]
    assert predict_hemoglobin(lo_p)["predicted_hb_g_dl"] < predict_hemoglobin(hi_p)["predicted_hb_g_dl"]
