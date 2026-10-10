# Backend integration guide

> **SIMULATED - NOT FOR MEDICAL USE.** The model was trained and evaluated only on synthetic
> images. Its output is a simulated hemoglobin-equivalent value, not a measurement, and it is
> not clinically validated. Show the `disclaimer` wherever the value is displayed.

## 1. What to copy

Keep this folder layout. By default the model is loaded from `<root>/models/hb_svr.joblib`;
you can pass `model_path=` instead.

```
<root>/
  src/aarogya_hb_ml/__init__.py
  src/aarogya_hb_ml/config.py
  src/aarogya_hb_ml/preprocessing.py
  src/aarogya_hb_ml/feature_extraction.py
  src/aarogya_hb_ml/inference.py
  models/hb_svr.joblib              # required
  models/hb_svr_metadata.json       # optional, readable copy of the metadata bundled in the model
  requirements-inference.txt
```

Inference does not need `data/`, `reports/`, `tests/` or the training modules. It also does not
need the demo SVM (`models/hb_demo_svm*`), which is an optional experimental artifact (section 7).

## 2. Environment

```bash
python -m pip install -r requirements-inference.txt
```

| package | pinned version |
|---|---|
| numpy | 2.5.3 |
| opencv-python-headless | 5.0.0.93 |
| scikit-learn | 1.9.1 |
| scipy | 1.18.1 |
| joblib | 1.6.0 |
| threadpoolctl | 3.7.0 |
| narwhals | 2.27.1 |
| cloudpickle | 3.1.2 |

- **Python:** verified only on CPython **3.14.8** (Windows, 64-bit). numpy 2.5.3 and scipy 1.18.1
  require Python >= 3.12. Python 3.12 / 3.13 and Linux / macOS are **untested**. The code contains
  no OS-specific paths.
- **Exact pins matter.** `hb_svr.joblib` is a pickled scikit-learn pipeline. With other
  scikit-learn or numpy versions it may fail to load (you get `status="model_unavailable"`) or
  give slightly different predictions. `get_model_info()["warnings"]` reports any version mismatch.
- The training and test environment is still `requirements.txt` (unchanged). pandas, matplotlib,
  pillow and pytest are not needed for inference.

## 3. Import

```python
import sys
sys.path.insert(0, "/path/to/<root>/src")      # or put <root>/src on PYTHONPATH

from aarogya_hb_ml.inference import predict_hemoglobin, get_model_info
```

These are the public entry points. There is **no** `analyze_strip` function; if your backend
expects that name, wrap `predict_hemoglobin` yourself.

## 4. `predict_hemoglobin(image_path, patient_info=None, model_path=..., expected_size=(512, 512)) -> dict`

**Inputs**

| argument | accepted |
|---|---|
| `image_path` | a file path (`str` / `pathlib.Path`) **or** encoded image bytes (`bytes`, `bytearray`, `memoryview`), e.g. `await upload.read()` |
| image content | an 8-bit, 3-channel, **512x512** image with one colored rectangle on white paper. Verified formats: PNG, JPEG, WEBP, BMP. Grayscale, 16-bit or other sizes return `load_failed`. `expected_size=None` turns off the size check; this is untested on real photos. |
| `patient_info` | optional and **not used**. If it is a dict, its keys are echoed in `patient_info_keys_received` along with a warning. |
| `model_path` | optional override for the model location |

**The function never raises.** Every problem returns `status != "ok"` with
`predicted_hb_g_dl = null` and `prediction_interval_g_dl = null`. It never makes up a value.

**Output.** Success and failure results have the same keys:

| key | type | meaning |
|---|---|---|
| `status` | str | `ok`, `invalid_input`, `load_failed`, `detection_failed`, `quality_failed`, `feature_extraction_failed`, `prediction_failed`, `model_unavailable`, `internal_error` |
| `predicted_hb_g_dl` | float (2 dp) / null | SVR estimate; null unless `status == "ok"` |
| `unit` | str | `"g/dL"` |
| `prediction_interval_g_dl` | [lo, hi] / null | ± the 90th percentile of out-of-fold error on synthetic data (1.04). Not a clinical confidence interval. |
| `interval_basis` | str / null | explains how the interval was computed |
| `quality_status` | str / null | preprocessing result |
| `quality_issues` | list[str] | reasons from the quality gate |
| `quality_metrics` | dict | sharpness, clipping, paper brightness, ROI uniformity, ROI size, detection confidence |
| `detection` | dict / null | `method`, `confidence`, `corners_xy` (pixels) |
| `warnings` | list[str] | e.g. extrapolation beyond the training data, or `patient_info` ignored |
| `failure_reason` | str / null | why no value was produced |
| `model_identifier`, `model_version` | str | provenance (`model_version` is null if the model did not load) |
| `source` / `clinically_validated` | str / bool | always `"synthetic"` / `false` |
| `disclaimer` | str | must be shown to users |
| `image` | str | **file name only**, or `"<bytes>"` / `"<none>"`. No field ever contains an absolute path. |
| `patient_info_keys_received` | list[str] | keys of `patient_info` |
| `timestamp_utc` | str | ISO-8601 |

Deliberately not returned: color features, any SVM class, any severity or anemia category, and any clinical interpretation.

## 5. `get_model_info(model_path=...) -> dict`

Loads and caches the model without running a prediction. Use it for `GET /api/models/info` and
`GET /api/health`. It never raises and never contains absolute paths.
`status` is `ok`, or `model_unavailable` with a `failure_reason`. Other fields: `model_identifier`,
`model_version`, `package_version`, `model_file`, `model_sha256`, `created_utc`, `estimator`,
`hyperparameters`, `target`, `unit`, `feature_set`, `n_features`, `feature_order`,
`training_target_range`, `prediction_interval_half_width_g_dl`, `validation_metrics`, `test_metrics`,
`dataset`, `input_contract`, `statuses`, `training_environment`, `runtime_environment`, `warnings`,
`experimental_artifacts`, `source`, `clinically_validated`, `disclaimer`, `limitations`.

## 6. Mapping to the existing FastAPI endpoints

The ML result is **not** a drop-in response model; map it to your backend schema explicitly.
The sketch below has not been run against your backend.

```python
from fastapi import FastAPI, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from aarogya_hb_ml.inference import get_model_info, predict_hemoglobin

app = FastAPI()
HTTP = {"ok": 200, "model_unavailable": 503, "internal_error": 500}   # every other status -> 422

@app.get("/api/health")
def health():
    ok = get_model_info()["status"] == "ok"
    return JSONResponse({"status": "ok" if ok else "degraded", "model_loaded": ok}, status_code=200 if ok else 503)

@app.get("/api/models/info")
def models_info():
    return get_model_info()

@app.post("/api/scans/analyze")
async def analyze(file: UploadFile):
    res = await run_in_threadpool(predict_hemoglobin, await file.read())   # never raises
    return JSONResponse({"measurement": res["predicted_hb_g_dl"], "result": res},
                        status_code=HTTP.get(res["status"], 422))
```

Measured locally: about 40 ms per image once loaded, and about 1 s for the first call, which loads the model.

**Fields the backend must map or adapt**

1. `predicted_hb_g_dl` → your measurement field. Keep it **null** on failure; never substitute a default.
2. `status` → your HTTP status and error code.
3. `failure_reason` / `quality_issues` → the user message (for example, "please retake the photo").
4. `source`, `clinically_validated`, `model_identifier`, `model_version`, `timestamp_utc` → store these with every scan.
5. `disclaimer` → always display it.
6. `prediction_interval_g_dl` → if you show it, label it as a synthetic error band.
7. `patient_info` → collect it if your product needs it; it does not affect the result.
8. Any severity or category fields in your schema → leave them empty. Do **not** derive them from this model or from the demo SVM.

## 7. Demo SVM (optional, experimental, not used by inference)

`models/hb_demo_svm.joblib` sorts the synthetic target range into three **artificial, equal-width
bands** (A 4.0-8.7, B 8.7-13.3, C 13.3-18.0) with no clinical meaning. It differed from simply
banding the SVR output on only 1 of 83 test images. `predict_hemoglobin` never loads or returns it,
and it must not be shown as a severity classification.

## 8. Limitations

- Synthetic data only: one invented color mapping, one contributor, 150 base samples. The test MAE of
  0.387 g/dL says nothing about real blood, real strips, real cameras or real patients.
- Works only on images that look like the training data: 512x512, one colored rectangle on white paper.
- White-paper normalization is not colorimetric calibration.
- The interval is a fixed synthetic error band, not a per-image uncertainty.
- Verified on Windows with Python 3.14.8 only.
- Model files are pickles. Load only `hb_svr.joblib` files produced by this project's training pipeline.

## 9. Replacing the model

Retrain with `run_pipeline.py`, using the training environment in `requirements.txt`. The model bundle
carries its own `feature_order` and metadata, so the inference code does not change. If you retrain
with different library versions, update `requirements-inference.txt` to match.
