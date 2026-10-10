# Aarogya Bindu — Synthetic Hemoglobin Assay Dataset Generator

> **SYNTHETIC DATA FOR SOFTWARE PROTOTYPING ONLY.**
> Images show simulated colorimetric reaction spots. Each image is paired with a
> *generator-assigned simulated hemoglobin-equivalent value* (`target_hb_g_dl`).
> The concentration-to-color mapping is an invented design choice. It is **not**
> based on real hemoglobin chemistry, has **no clinical calibration**, and these
> targets are **not** measured hemoglobin concentrations. Models trained on this data
> are not validated for real assays or clinical use.

This tool makes reproducible PNG images of a white paper assay card with one
rectangular reaction spot. Each image has a manifest row so the backend team
can build and test spot detection, color-feature extraction and regression
before real experimental data is available.

---

## 1. Installation

You need Python 3.10 or newer. It was developed and tested with Python 3.14.8,
numpy 2.5, OpenCV 5.0, Pillow 12.3, pandas 3.0, matplotlib and scikit-learn 1.9.

```powershell
# Windows PowerShell, from the project folder
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

You don't need to install the package itself. `run_generator.py` adds `src/`
to the import path. The commands below use `python`, meaning the virtual
environment's interpreter (`.\.venv\Scripts\python.exe` on Windows).

## 2. Quick start (one command)

```powershell
python run_generator.py all --config configs/pilot.json --output aarogya_synthetic_dataset
```

This command:

1. Generates the dataset: 150 base samples × 4 variants = 600 images. This takes about 2 minutes.
2. Runs every quality check.
3. Creates the preview grid and reports.

It exits with code 0 only if validation passes.

You can also run the steps one at a time:

```powershell
python run_generator.py generate --config configs/pilot.json --output aarogya_synthetic_dataset
python run_generator.py validate --dataset aarogya_synthetic_dataset
python run_generator.py report   --dataset aarogya_synthetic_dataset
python run_generator.py inspect-mapping --config configs/pilot.json      # print mapping table
python scripts/example_load_dataset.py --dataset aarogya_synthetic_dataset
python -m unittest discover -s tests -t .                                # unit tests
```

| option | meaning |
|---|---|
| `--config PATH` | JSON config. Keys you leave out use the built-in defaults, which equal `configs/pilot.json`. |
| `--output PATH` | Dataset folder. Relative paths resolve from the current directory. |
| `--num-base-samples N` | Overrides the number of independent base samples. |
| `--generation-seed S` / `--split-seed S` | Overrides the seeds. |
| `--append` | Adds a new batch to an existing dataset (see §8). |
| `validate --rerender K` | Number of rows to re-render for the pixel-exact reproducibility check. `0` skips it. |
| `-v` | Debug logging. |

Exit codes:

- `0`: success.
- `1`: validation failed.
- `2`: configuration or generation error. Generation stops with a clear message.

## 3. Project layout

```
aarogya_bindu_dataset_generator/
├── requirements.txt
├── run_generator.py              # CLI launcher (python run_generator.py <command>)
├── configs/pilot.json            # documented default/pilot configuration
├── src/aarogya_synth/
│   ├── config.py                 # dataclass config, JSON loading, validation, config hash
│   ├── seeding.py                # seed derivation (generation vs. split streams)
│   ├── colorspace.py             # sRGB <-> CIELAB (D65) in NumPy
│   ├── color_mapping.py          # target -> color ONLY (synthetic + calibration-table mappings)
│   ├── rendering.py              # clean card and print/paper variation
│   ├── augmentation.py           # geometry, lighting, white balance, blur, noise (seeded)
│   ├── splits.py                 # stratified, leakage-free base-sample splits
│   ├── features.py               # reference spot detector + color features (backend reference)
│   ├── manifest.py               # CSV schema / data contract
│   ├── generate.py               # orchestration, per-image checks, safe writing/appending
│   ├── validation.py             # dataset quality checks + validation report
│   ├── reports.py                # preview grid, plots, summaries
│   ├── readme.py                 # dataset card (README.md inside each dataset)
│   └── cli.py                    # command-line interface
├── scripts/example_load_dataset.py   # backend example: load, verify, extract features
└── tests/                        # unittest suite
```

Generated dataset:

```
aarogya_synthetic_dataset/
├── images/sample_000001.png ...      # opaque names, no labels
├── manifest.csv                      # one row per image
├── generation_config.json            # resolved config, mapping description, seeds, library versions
├── README.md                         # dataset card
├── previews/preview_grid.png
└── reports/
    ├── validation_report.md / .json
    ├── color_mapping_curve.png, color_mapping_table.csv
    ├── split_summary.csv, split_target_distributions.png
    ├── augmentation_summary.md / .csv
    └── dataset_summary.md
```

## 4. Image specification and coordinates

- 512 × 512 px, 8-bit RGB PNG with no alpha channel. Readable by Pillow, OpenCV, imageio and matplotlib.
- White background (255, 255, 255) representing a plain paper card.
- One rectangular reaction spot. By default it is at `spot_x=176, spot_y=196`, size 160 × 120, which centers it at (256, 256).
- No text, icons, logos, alignment markers or reference patches.
- **Coordinate convention:**
  - The origin (0, 0) is the top-left corner. x increases to the right (columns) and y increases downward (rows).
  - Pixel (i, j) covers the area [i, i+1) × [j, j+1).
  - The clean spot covers columns `spot_x … spot_x+spot_width-1` and rows `spot_y … spot_y+spot_height-1`.
  - `spot_corners_xy` gives the transformed corners in continuous coordinates, in the order top-left, top-right, bottom-right, bottom-left.

## 5. Synthetic concentration-to-color mapping

The mapping lives in `color_mapping.py`, separate from rendering. It is **a design choice, not a calibration curve.**

For a simulated target *c* (g/dL):

```
t      = clip((c − c_min) / (c_max − c_min), 0, 1)
s      = t ** gamma                         # gamma > 0 → strictly increasing
Lab(c) = Lab_low + s · (Lab_high − Lab_low) # CIELAB, D65 white
RGB8   = round(255 · sRGB(Lab(c)))          # Lab → XYZ → linear RGB → sRGB gamma
```

| parameter | default | meaning |
|---|---|---|
| `target_min`, `target_max` | 4.0, 18.0 | simulated range in g/dL |
| `gamma` | 1.0 | curve shape (1 = linear in Lab) |
| `lab_low` | (86, 8, 38) | pale yellow-orange at `target_min`, RGB ≈ (254, 208, 143) |
| `lab_high` | (38, 45, 28) | deep red-brown at `target_max`, RGB ≈ (161, 51, 47) |

Properties:

- **Deterministic:** the result depends only on the target and the config.
- **Smooth:** a 0.01 g/dL step changes any 8-bit channel by at most 2.
- **Monotonic:** L\* strictly decreases as the target rises, so higher targets give darker spots.
- **In gamut:** 1,001 points on the curve are checked when the mapping is built. A configuration whose curve leaves the sRGB gamut raises an error instead of being clipped silently.
- **Stored with the dataset:** the equation and parameters are saved in `generation_config.json → mapping_description`, and a sampled table is saved in `reports/color_mapping_table.csv`.
- **Labels and rounding:** targets are rounded to `target_decimals` (default 2), and the rounded value is the one used to compute the color, so the label is exactly the value that produced the color.
- **Resolution limit:** 8-bit quantization limits clean color resolution to roughly one L\* step per 0.3 g/dL.

## 6. Image-variation (augmentation) pipeline

Each base sample yields a **clean** image (deterministic; spot pixels are exactly the mapped color)
plus one image per severity profile: `mild`, `moderate`, `challenging`. An augmented image is a pure
function of `(config, target, profile, random_seed)`. Stages run in a fixed order, and every drawn
parameter is recorded in the manifest:

1. **Print/paper variation:** small Lab offset of the printed color (ΔE ≤ `print_delta_e_max`), an L\*
   gradient across the spot, a slightly darker rim, soft edges and smooth paper texture.
2. **Geometry:** rotation, scale, translation and perspective jitter as one homography. Draws repeat until
   every spot corner is at least `min_margin_px` inside the frame.
3. **Uneven illumination:** linear or radial gradient.
4. **Soft shadow:** with a given probability, a heavily blurred darkened region.
5. **White balance:** per-channel gains.
6. **Contrast, then brightness:** `y = b · (k · (x − 128) + 128)`.
7. **Blur:** Gaussian blur (`blur_level` = sigma) plus optional disk defocus.
8. **Gaussian sensor noise** (`noise_level`, 8-bit units), then clip and round to uint8.

| range | mild | moderate | challenging |
|---|---|---|---|
| brightness | 0.95–1.05 | 0.88–1.12 | 0.78–1.22 |
| contrast | 0.95–1.05 | 0.90–1.10 | 0.80–1.20 |
| white-balance gain | ±3 % | ±7 % | ±12 % |
| illumination amplitude | ≤ 5 % | ≤ 12 % | ≤ 22 % |
| shadow prob. / strength | 0.1 / 3–10 % | 0.3 / 5–20 % | 0.6 / 10–35 % |
| blur sigma (px) | 0–0.6 | 0.5–1.3 | 1.0–2.5 |
| defocus prob. / radius | 0 | 0.2 / 1–2 px | 0.35 / 1.5–3 px |
| noise sigma (8-bit) | 0–2 | 2–5 | 4–10 |
| rotation | ±2° | ±5° | ±10° |
| perspective | ≤ 0.01 | ≤ 0.025 | ≤ 0.045 |
| scale / translation | ±3 % / ±10 px | ±6 % / ±25 px | ±10 % / ±45 px |
| print ΔE / spot gradient ΔL\* | ≤ 0.75 / ≤ 1 | ≤ 1.5 / ≤ 2 | ≤ 2.5 / ≤ 3.5 |

Every value can be changed per profile (`profiles.<name>.<key>`). New profile names can be added and listed in `variants`.

**Label preservation (documented limitation):**

- Geometry, blur, noise and print variation keep the label meaningful.
- **Brightness, contrast, white balance, illumination and shadows deliberately change the *apparent* spot
  color while the label stays the same.** This mimics an uncalibrated phone camera.
  - The default card has no reference patches, so a model can't fully undo these shifts.
  - Each image records the size of the shift as `apparent_delta_e_vs_clean` (CIE76). Use it to stratify,
    filter or weight images, or start by training on `clean` and `mild` only.
- `challenging` can shift colors by an amount comparable to several g/dL of the synthetic mapping. Treat it as a stress test.

**Generation-time checks:** each augmented image must:

- have the right shape and dtype;
- not be nearly uniform;
- keep the spot inside the margin;
- keep spot-versus-paper ΔE ≥ 10;
- let the reference detector find the spot with IoU ≥ 0.6.

If an image fails, it is redrawn with `attempt + 1`, which gives a new derived seed. This is recorded in
`generation_attempt` and in `generation_config.json → batches[].regenerations`. After `max_attempts`
failures, generation stops with an error.

## 7. Random seeds and reproducibility

- **`generation_seed`** drives target sampling and each image's seed:
  `random_seed = SeedSequence(generation_seed, spawn_key=(2, batch, base_index, variant_index, attempt))`.
- **`split_seed`** drives only the train/val/test assignment. Changing it never changes any pixel or target.
- `random_seed` alone reproduces an image: `render_variant(cfg, mapping, target, profile, random_seed)`.
  `validate` re-renders a sample of rows and checks that the pixels match exactly.
- Library versions are recorded in `generation_config.json`. Pixel-exact output across different OpenCV,
  NumPy or Pillow versions is **not** guaranteed, but labels and parameters are.
- Targets come from stratified-uniform sampling (one jittered draw per equal-width bin, then shuffled),
  so the order of IDs carries no information about the target.

## 8. Splits, dataset size and appending

**How splits are assigned:**

- Splits are assigned to **independent base samples before any augmentation**, using a default ratio of 70 / 15 / 15.
- Assignment is stratified:
  1. Base samples are sorted into `stratify_bins` target-quantile bins.
  2. Each bin is shuffled using `split_seed`.
  3. Base samples are interleaved proportionally, which gives exact overall counts and similar target coverage in each split.
- All variants of a base sample inherit its split, so augmentations of one base sample can **never** appear in different splits. The validator re-checks this.

**Using the test split:**

- Keep `test` untouched during model development.
- A random synthetic test split does **not** demonstrate clinical validity or generalization to real assay chemistry.

**Dataset size:** `num_base_samples × len(variants)` images. The pilot is 150 × 4 = 600. Scale up only after the pilot passes validation.

**Appending:**

```powershell
python run_generator.py generate --config aarogya_synthetic_dataset/generation_config.json `
    --output aarogya_synthetic_dataset --append --num-base-samples 50 --generation-seed 20261011
```

**Overwrite protection:**

- **Without `--append`:** generation refuses to write into a non-empty folder.
- **With `--append`:**
  - The core configuration hash must match the existing dataset. That covers image, mapping, profiles, variants, splits and checks.
  - New base samples, image IDs and filenames continue after the existing ones.
  - The new batch is split on its own.
  - Images are staged first and moved into place only after the whole batch succeeds.
  - Existing files are never overwritten.
- After appending, run `validate` and `report` again.

## 9. Manifest (`manifest.csv`) — data contract

There is one row per image, UTF-8 encoded, with a header row. The first 18 columns are the required contract; the rest are extended metadata.

- **Labels:** labels exist **only** in `target_hb_g_dl`. They never appear in pixels or filenames.
- **JSON columns:** these contain compact JSON strings.

| column | type | description |
|---|---|---|
| `image_id` | str | Unique opaque ID, e.g. `IMG000001` |
| `relative_image_path` | str | POSIX path relative to the dataset root, e.g. `images/sample_000001.png` |
| `base_sample_id` | str | Independent base sample, e.g. `B000001`. Shared by its clean image and all of its variants. |
| `target_hb_g_dl` | float | **Simulated** hemoglobin-equivalent target in g/dL, assigned by the generator. It is not a measurement. |
| `dataset_split` | str | `train` / `val` / `test` |
| `random_seed` | int | Per-image seed |
| `augmentation_profile` | str | `clean` / `mild` / `moderate` / `challenging` |
| `brightness_factor`, `contrast_factor` | float | 1.0 means no change |
| `blur_level` | float | Gaussian blur sigma in px |
| `noise_level` | float | Noise sigma in 8-bit units |
| `illumination_profile` | json | e.g. `{"amplitude":0.08,"angle_deg":31.2,"type":"linear"}` |
| `white_balance_profile` | json | `{"b":..,"g":..,"r":..}` gains |
| `rotation_degrees` | float | In-plane rotation |
| `perspective_strength` | float | Maximum corner jitter as a fraction of the image size |
| `image_width`, `image_height` | int | Pixels |
| `dataset_type` | str | Always `synthetic` |
| `variant_index`, `generation_batch`, `generation_attempt` | int | Provenance |
| `scale_factor`, `translate_x_px`, `translate_y_px`, `defocus_radius_px` | float | Geometry and optics |
| `shadow_profile`, `print_profile` | json | Shadow and print-variation parameters |
| `print_delta_e` | float | Printed-color offset (CIE76) |
| `apparent_delta_e_vs_clean` | float | ROI median Lab distance from the clean image of the same base sample |
| `spot_corners_xy` | json | True spot corners TL, TR, BR, BL. **For training and debugging only, never as an inference input.** |
| `mapping_id`, `image_sha256`, `generator_version` | str | Provenance and integrity |

## 10. Backend integration guide

**Inference input:**

- A PNG or JPEG photo.
- At inference time the backend must **not** need `target_hb_g_dl`, the manifest, the filename or `spot_corners_xy`.

**Labels:** `target_hb_g_dl` in `manifest.csv`, for training and evaluation only.

```python
from pathlib import Path
import pandas as pd
from aarogya_synth.features import load_rgb, extract_features   # reference implementation

root = Path("aarogya_synthetic_dataset")
df = pd.read_csv(root / "manifest.csv")
dev = df[df.dataset_split.isin(["train", "val"])]     # keep "test" untouched while developing

X, y = [], []
for row in dev.itertuples():
    rgb = load_rgb(root / row.relative_image_path)    # uint8 RGB, H x W x 3
    feats = extract_features(rgb)                     # spot detected from pixels only
    X.append(feats)
    y.append(row.target_hb_g_dl)                      # label joined from the manifest
X = pd.DataFrame(X)
```

`scripts/example_load_dataset.py` does three things:

1. Checks that every manifest row points to an existing image with a matching SHA-256 and a numeric label, and that no base sample is in more than one split.
2. Extracts features from a few train and val images.
3. Prints them next to their labels.

**Reference spot detector (`features.detect_spot`):**

1. Compute a saturation map, `(max − min) / max`, after a light blur.
2. Threshold it at several levels, including Otsu's threshold, then clean up with morphology.
3. Discard contours that touch the image border (for example tinted shadows) or that aren't rectangular (fill < 0.8 of the min-area rectangle).
4. Pick the largest remaining one with `minAreaRect`, giving 4 corners.

The analysis ROI is that rectangle shrunk 15 % toward its center, which avoids soft edges and the rim.

**Features (`features.extract_features`):**

| group | keys |
|---|---|
| median / mean RGB | `rgb_median_{r,g,b}`, `rgb_mean_{r,g,b}`, `rgb_std_{r,g,b}` (0–255) |
| HSV | `hsv_h_circmean_deg`, `hsv_h_circstd_deg` (0–360°, circular), `hsv_{s,v}_{mean,std}` (0–1) |
| CIELAB | `lab_{l,a,b}_{mean,median,std}`: true L\*a\*b\* (D65), **not** OpenCV's 8-bit scaled Lab |
| variation within the ROI | the `*_std` keys above, `lab_l_iqr`, `roi_pixel_count`, `roi_area_fraction` |

**Notes for the backend:**

- OpenCV loads images as **BGR**. `load_rgb` converts them to RGB.
- OpenCV's 8-bit HSV uses H in 0–179. These features use degrees.
- Real phone photos will need a stronger detector (card detection plus perspective correction) and real JPEG/ISP handling.

## 11. Quality checks (`validate`)

| check | what it verifies |
|---|---|
| manifest_structure | all columns present, no missing required values, `dataset_type == synthetic`, known profiles |
| duplicate_ids_and_filenames | unique IDs and paths (also case-insensitive); one image per (base sample, profile) |
| targets_valid_and_consistent | numeric, finite, within range; one target per base sample |
| target_range_and_distribution | histogram coverage of the configured range (WARN if bins are empty or uneven) |
| splits_and_leakage | valid split names; **no base sample in two splits**; non-empty splits; fractions |
| mapping_config_stored_and_consistent | stored mapping description equals the rebuilt mapping; `mapping_id` matches |
| image_files_exist_and_readable | every row's file exists and decodes |
| image_dimensions_and_rgb_values | 512×512×3, uint8, manifest size equals file size |
| manifest_hash_matches_file | file SHA-256 equals `image_sha256` (detects later edits) |
| files_without_manifest_entry | no orphan images in `images/` |
| uniform_or_featureless_images | no near-constant images |
| duplicate_image_content | identical pixels. **Expected** (WARN): clean images whose targets map to the same 8-bit color, i.e. identical generation settings. In the pilot, 9 pairs of targets 0.01–0.05 g/dL apart do this because of 8-bit quantization, and the report lists the label spread. **Suspicious** (FAIL): anything else, such as colliding augmented images. Nothing is deleted. |
| spot_detectable_by_reference_detector | detector IoU ≥ 0.6 against the true corners |
| clean_color_mapping_monotonicity | clean spot pixels equal the mapping color exactly; measured L\* is monotonic in target (ties from 8-bit rounding are WARN) |
| reproducibility_rerender | sampled rows re-render pixel-identically from `random_seed` |

## 12. Configuration reference

`configs/pilot.json` lists every option and its default value. Any key you leave out falls back to the same built-in default. Unknown keys are rejected so that typos fail loudly instead of being ignored, and keys that start with `_` are treated as comments.

| section | keys |
|---|---|
| top level | `num_base_samples`, `generation_seed`, `split_seed`, `target_decimals`, `variants` |
| `image` | `width`, `height`, `background_rgb`, `spot_x`, `spot_y`, `spot_width`, `spot_height` |
| `mapping` | `type` (`synthetic_lab_linear` \| `calibration_table`), `mapping_id`, `target_min`, `target_max`, `gamma`, `lab_low`, `lab_high`, `calibration_table_csv` |
| `splits` | `train`, `val`, `test`, `stratify_bins` |
| `checks` | `max_attempts`, `min_margin_px`, `require_detectable_spot`, `min_detection_iou`, `min_spot_paper_delta_e` |
| `profiles.<name>` | the ranges listed in §6 |

## 13. Replacing the synthetic mapping with real data

1. Collect real assay photos under controlled conditions. Each one needs an **independently measured** reference hemoglobin value from a validated laboratory method.
2. Extract the spot color with the same ROI method, ideally after color correction with reference patches, and convert it to CIELAB.
3. Fit and validate a monotonic calibration. Export it as a table with columns `target_hb_g_dl,L,a,b` and strictly increasing targets.
4. Point the config at the table:

   ```json
   "mapping": {"type": "calibration_table", "mapping_id": "lab_calibration_v1",
               "calibration_table_csv": "calibration.csv", "target_min": 4.0, "target_max": 18.0}
   ```

   `CalibrationTableMapping` interpolates piecewise-linearly and applies the same gamut and monotonicity checks. The renderer, augmentations, manifest and validator don't need to change.

Images rendered from a real calibration table are still **simulated**. Real performance has to be measured on real photos with reference values, kept separate from the synthetic data.

## 14. Known limitations

- **Synthetic mapping:** the mapping is invented and has no clinical calibration. It does not model hemoglobin chemistry, reaction kinetics or timing, sample volume, hematocrit, interferents, paper absorbency or reagent batches.
- **Simple variation models:** the augmentations are simple parametric models, not physically based rendering. They don't simulate specular glare, JPEG compression, phone ISP processing (tone mapping, sharpening, auto white balance), sensor spectral response or card curvature.
- **Lighting confound:** photometric augmentations shift the apparent color and there are no reference patches, so `challenging` images are partly ambiguous by design (§6).
- **Color resolution:** 8-bit color limits clean resolution to roughly 0.3 g/dL per L\* step.
- **What a good test score means:** a good score on the synthetic test split only shows that the pipeline can recover this synthetic mapping. It is not evidence of real assay accuracy, and this tool reports no model accuracy.
- **Reproducibility across versions:** pixel-exact reproducibility requires identical library versions.
- **Reference detector scope:** the reference detector is tuned for these synthetic cards.
