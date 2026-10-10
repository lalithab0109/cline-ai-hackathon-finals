# aarogya-bindu-ml

> **SIMULATED - NOT FOR MEDICAL USE.** This pipeline is trained and evaluated only on
> synthetic images whose colors come from an invented target-to-color mapping
> (`synthetic_lab_linear_v1`). Its output is a *simulated hemoglobin-equivalent value*,
> not a hemoglobin measurement. It is not clinically validated.

Predicts `target_hb_g_dl` from a 512x512 synthetic colorimetric spot image, using OpenCV preprocessing, hand-crafted color features and an SVR.

## Setup

```powershell
py -3 -m venv .venv            # or the full path to python.exe
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- `requirements.txt`: training, evaluation and tests (minimum versions).
- `requirements-inference.txt`: **exact** pinned versions for serving the saved model. Verified only on
  Python 3.14.8 / Windows; requires Python >= 3.12. See `INTEGRATION.md`.

## Run

```powershell
.venv\Scripts\python.exe run_pipeline.py          # all stages (~1-2 min)
.venv\Scripts\python.exe -m pytest -q tests       # 57 tests
$env:PYTHONPATH="src"; .venv\Scripts\python.exe -m aarogya_hb_ml.inference path\to\image.png
$env:PYTHONPATH="src"; .venv\Scripts\python.exe -m aarogya_hb_ml.inference --info   # model metadata
```

Python API: `from aarogya_hb_ml.inference import predict_hemoglobin, get_model_info`. Neither function raises.
Every failure returns `predicted_hb_g_dl = null`, and no result contains absolute file paths.

Stages (each one can also be run as `python -m aarogya_hb_ml.<module>` with `PYTHONPATH=src`):

| stage | module | outputs |
|---|---|---|
| 1 | `prepare_data` | `reports/dataset_validation.md`, `data/splits/splits.csv`, `data/processed/features.csv`, `reports/preprocessing/*.png` |
| 2 | `train_svr` | `models/hb_svr.joblib`, `models/hb_svr_metadata.json` |
| 3 | `train_svm` | `models/hb_demo_svm.joblib` (demo only, artificial bands) |
| 4 | `evaluation` | `reports/evaluation.md/.json`, plots |

## Data and contributors

Sources are registered in `data/sources.json`. Each source is a folder containing `manifest.csv`, `generation_config.json` and `images/`. Sources are merged **only if their mapping descriptions are identical**; otherwise loading stops with an error. Labels come only from the `target_hb_g_dl` column of the manifest. The ground-truth corners in the manifest are never used.

Currently there is **one** contributor (`contrib_a`, 600 images, 150 base samples). Comparisons between contributors are not possible until a second compatible dataset is added.

## Method

- **Splits:** images are grouped by `base_sample_id`. Groups whose images are pixel-identical are merged via union-find (9 pairs are identical because of 8-bit quantization). The groups are then split 70/15/15, stratified by target quintile, with seed 2026. No group spans more than one split, and this is tested.
- **Detection:** colorfulness map, multi-threshold contours, and plausibility filters (area, border, rectangularity, aspect). The quad is approximated, then perspective-rectified to 160x120. The interior ROI excludes an 18% margin. No fixed coordinates are used.
- **Quality gate:** blocks on low detection confidence, ≥5% of ROI pixels with ≥2 saturated channels, dark paper, blur, a small ROI, or a non-uniform ROI. A blocked image yields **no number**.
- **Normalization (not calibration):** the ROI color is divided by the paper-white estimate taken from a ring around the spot. This corrects global brightness and tint only to the extent that the paper is white and evenly lit. There are no reference patches, so true calibration is impossible.
- **Features:** two sets, `raw_color` (21) and `normalized` (30). They cover RGB, Lab, circular hue, chromaticity, ratios, absorbance and contrast to the background.
- **Model selection:** SVR with linear and RBF kernels × both feature sets, tuned by GroupKFold(5) grid search on train. The candidate with the lowest val MAE is chosen, refit on train+val, and evaluated **once** on test. The baselines are a mean predictor and linear regression.

## Results (test, n=83, from `reports/evaluation.md`)

| model | MAE | RMSE | R² |
|---|---|---|---|
| **SVR RBF, normalized features** (C=10, γ=0.01, ε=0.05) | **0.387** | 0.582 | 0.981 |
| Linear regression, normalized | 0.445 | 0.644 | 0.977 |
| Mean predictor | 3.748 | 4.287 | -0.017 |

Test MAE by profile: clean 0.12, mild 0.18, moderate 0.46, challenging 0.81. Error grows with brightness, blur and noise; see `error_vs_conditions.png`. One test image (challenging, overexposed) was excluded by the quality gate.

The R² values per target range in the report are computed within narrow ranges and are not meaningful, so use the MAE values there instead.

The demo SVM is an **optional experimental artifact**. It uses three equal-width **artificial** bands with no clinical meaning. Its test balanced accuracy is 0.95, against 0.94 for simply cutting the SVR output into the same bands; the two disagree on 1 of 83 test images. Inference never loads or returns it.

## Limitations

- All metrics measure how well the pipeline can invert a known synthetic color mapping under simulated capture variation. They say **nothing** about real blood, real strips, real cameras or real patients.
- 150 base samples, one generator and one contributor.
- The interval is ± the 90th percentile of the out-of-fold absolute error on synthetic data. It is not a clinical confidence interval.
- `patient_info` is accepted but not used.
