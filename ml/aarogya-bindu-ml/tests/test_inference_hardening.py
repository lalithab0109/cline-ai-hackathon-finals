"""Focused tests for inference hardening: input validation, model-load failures, path redaction, get_model_info."""

import json
import re
from pathlib import Path

import cv2
import joblib
import numpy as np
import pandas as pd
import pytest
from conftest import make_strip, save_rgb

from aarogya_hb_ml import config as C
from aarogya_hb_ml import inference as inf
from aarogya_hb_ml.inference import get_model_info, predict_hemoglobin

needs_model = pytest.mark.skipif(not C.SVR_MODEL_FILE.is_file(), reason="model not trained")
ABS_PATH = re.compile(r"[A-Za-z]:[\\/]|\\\\|(^|[\s'\"(])/[^\s/]+/")
BASE_KEYS = {"status", "predicted_hb_g_dl", "unit", "prediction_interval_g_dl", "interval_basis", "quality_status",
             "quality_issues", "quality_metrics", "detection", "warnings", "failure_reason", "model_identifier",
             "model_version", "source", "clinically_validated", "disclaimer", "image", "patient_info_keys_received",
             "timestamp_utc"}


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def assert_no_abs_paths(result):
    leaks = [s for s in _strings(result) if ABS_PATH.search(s)]
    assert not leaks, leaks


def assert_structured_failure(r, status=None):
    assert set(r) == BASE_KEYS
    assert r["status"] != "ok" and (status is None or r["status"] == status)
    assert r["predicted_hb_g_dl"] is None and r["prediction_interval_g_dl"] is None and r["interval_basis"] is None
    assert r["failure_reason"]
    assert r["source"] == "synthetic" and r["clinically_validated"] is False
    json.dumps(r)
    assert_no_abs_paths(r)


@needs_model
@pytest.mark.parametrize("bad", [None, "", "   ", 123, 4.5, object(), ["a.png"], {"path": "x"}])
def test_invalid_inputs_return_structured_failure(bad):
    assert_structured_failure(predict_hemoglobin(bad), "invalid_input")


@needs_model
def test_empty_bytes_and_bytes_like_inputs():
    assert_structured_failure(predict_hemoglobin(b""), "load_failed")
    rgb, _ = make_strip()
    data = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))[1].tobytes()
    a, b = predict_hemoglobin(bytearray(data)), predict_hemoglobin(memoryview(data))
    assert a["status"] == b["status"] == "ok" and a["predicted_hb_g_dl"] == b["predicted_hb_g_dl"]
    assert a["image"] == "<bytes>" == b["image"]


def test_missing_model_file(tmp_path, strip_png):
    r = predict_hemoglobin(strip_png, model_path=tmp_path / "absent.joblib")
    assert_structured_failure(r, "model_unavailable")
    assert "absent.joblib" in r["failure_reason"]


@pytest.mark.parametrize("content", [b"", b"not a pickle at all", b"\x80\x04\x95garbage"])
def test_corrupt_model_file(tmp_path, strip_png, content):
    bad = tmp_path / "corrupt.joblib"
    bad.write_bytes(content)
    assert_structured_failure(predict_hemoglobin(strip_png, model_path=bad), "model_unavailable")
    info = get_model_info(bad)
    assert info["status"] == "model_unavailable" and info["failure_reason"]
    assert_no_abs_paths(info)


def test_wrong_bundle_contents(tmp_path, strip_png):
    p1, p2 = tmp_path / "list.joblib", tmp_path / "partial.joblib"
    joblib.dump([1, 2, 3], p1)
    joblib.dump({"pipeline": None, "metadata": {}}, p2)
    for p in (p1, p2):
        assert_structured_failure(predict_hemoglobin(strip_png, model_path=p), "model_unavailable")


@needs_model
def test_prediction_exception_is_contained(monkeypatch, strip_png):
    bundle = dict(inf.load_model())

    class Boom:
        def predict(self, x):
            raise RuntimeError(r"boom at C:\secret\dir\model.py")

    bundle["pipeline"] = Boom()
    monkeypatch.setattr(inf, "load_model", lambda path=None: bundle)
    r = predict_hemoglobin(strip_png)
    assert_structured_failure(r, "prediction_failed")
    assert "model.py" in r["failure_reason"] and "secret" not in r["failure_reason"]


@needs_model
def test_unexpected_exception_becomes_internal_error(monkeypatch, strip_png):
    def explode(*a, **k):
        raise MemoryError("simulated")

    monkeypatch.setattr(inf, "preprocess", explode)
    assert_structured_failure(predict_hemoglobin(strip_png), "internal_error")


@needs_model
def test_success_response_has_no_absolute_paths_and_same_schema():
    path = pd.read_csv(C.DATASET_CSV)["abs_path"].iloc[0]
    r = predict_hemoglobin(path)
    assert r["status"] == "ok" and set(r) == BASE_KEYS
    assert r["image"] == Path(path).name
    assert_no_abs_paths(r)


@needs_model
@pytest.mark.parametrize("kind", ["missing", "corrupt", "blank"])
def test_failure_messages_do_not_leak_paths(tmp_path, kind):
    if kind == "missing":
        p = tmp_path / "nowhere" / "img.png"
    elif kind == "corrupt":
        p = tmp_path / "c.png"
        p.write_bytes(b"\x89PNG\r\n broken")
    else:
        p = save_rgb(tmp_path / "blank.png", np.full((512, 512, 3), 240, np.uint8))
    r = predict_hemoglobin(str(p))
    assert_structured_failure(r)
    assert r["image"] == p.name


@needs_model
def test_non_dict_patient_info_is_ignored_with_warning(strip_png):
    r = predict_hemoglobin(strip_png, patient_info=["age"])
    assert r["status"] == "ok" and r["patient_info_keys_received"] == []
    assert any("patient_info ignored" in w for w in r["warnings"])


def test_redact_helper():
    msg = r"file not found: C:\Users\someone\x\img.png; also /home/u/data/a.png and \\server\share\b.png"
    out = inf._redact(msg)
    assert "img.png" in out and "a.png" in out and "b.png" in out
    assert "someone" not in out and "/home" not in out and "server" not in out
    for safe in ("+/- 90th percentile in g/dL", "overexposed_or_clipped_roi (29.0% > 5%)"):
        assert inf._redact(safe) == safe


@needs_model
def test_get_model_info_matches_metadata_without_prediction(monkeypatch):
    monkeypatch.setattr(inf, "preprocess", lambda *a, **k: pytest.fail("get_model_info must not predict"))
    info = get_model_info()
    meta = json.loads(C.SVR_META_FILE.read_text(encoding="utf-8"))
    assert info["status"] == "ok" and info["failure_reason"] is None
    assert info["model_identifier"] == meta["model_identifier"] and info["model_version"] == meta["model_version"]
    assert info["feature_order"] == meta["feature_order"] and info["n_features"] == 30
    assert info["test_metrics"] == meta["test_metrics"] and info["created_utc"] == meta["created_utc"]
    assert info["source"] == "synthetic" and info["clinically_validated"] is False
    assert info["limitations"] and info["disclaimer"]
    assert len(info["model_sha256"]) == 64 and info["model_file"] == "hb_svr.joblib"
    assert info["experimental_artifacts"]["demo_svm"]["used_by_inference"] is False
    json.dumps(info)
    assert_no_abs_paths(info)


def test_get_model_info_missing_model(tmp_path):
    info = get_model_info(tmp_path / "none.joblib")
    assert info["status"] == "model_unavailable" and "none.joblib" in info["failure_reason"]
    assert info["clinically_validated"] is False
    json.dumps(info)
    assert_no_abs_paths(info)


@needs_model
def test_svm_is_never_loaded_or_returned(monkeypatch, strip_png):
    real_load = joblib.load

    def guarded(path, *a, **k):
        assert "svm" not in Path(path).name.lower(), "inference must not load the SVM"
        return real_load(path, *a, **k)

    monkeypatch.setattr(inf, "_MODEL_CACHE", {})
    monkeypatch.setattr(inf.joblib, "load", guarded)
    r = predict_hemoglobin(strip_png)
    assert r["status"] == "ok"
    assert not [k for k in r if any(s in k.lower() for s in ("svm", "band", "class", "severity", "anemia"))]


@needs_model
def test_saved_test_predictions_unchanged():
    """Inference reproduces the SVR test predictions saved at training time (up to 2-dp rounding)."""
    idx = pd.read_csv(C.DATASET_CSV).set_index("uid")
    saved = pd.read_csv(C.PROCESSED_DIR / "svr_test_predictions.csv")
    assert len(saved) == 83
    for row in saved.itertuples():
        r = predict_hemoglobin(idx.loc[row.uid, "abs_path"])
        assert r["status"] == "ok"
        assert r["predicted_hb_g_dl"] == pytest.approx(row.svr_pred, abs=0.0051)
