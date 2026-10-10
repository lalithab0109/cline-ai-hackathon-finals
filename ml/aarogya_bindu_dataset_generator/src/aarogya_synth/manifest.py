"""Manifest schema (data contract with the backend) and safe read/write helpers.

``manifest.csv`` has exactly one row per image file. Column order is fixed by
``MANIFEST_COLUMNS``. Labels live only here - never in pixels or filenames.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

MANIFEST_NAME = "manifest.csv"
CONFIG_NAME = "generation_config.json"

# (column, dtype, description) - also rendered into the README / dataset card.
SCHEMA: list[tuple[str, str, str]] = [
    ("image_id", "str", "Unique opaque image id, e.g. IMG000001 (no label information)"),
    ("relative_image_path", "str", "POSIX path relative to the dataset root, e.g. images/sample_000001.png"),
    ("base_sample_id", "str", "Independent base sample, e.g. B000001; shared by its clean image and all variants"),
    ("target_hb_g_dl", "float", "SIMULATED hemoglobin-equivalent target (g/dL) assigned by the generator; NOT a measurement"),
    ("dataset_split", "str", "train | val | test (assigned per base sample)"),
    ("random_seed", "int", "Per-image seed; numpy.random.default_rng(random_seed) reproduces the variation"),
    ("augmentation_profile", "str", "clean | mild | moderate | challenging"),
    ("brightness_factor", "float", "Multiplicative brightness (1.0 = none)"),
    ("contrast_factor", "float", "Contrast about mid-grey 128 (1.0 = none)"),
    ("blur_level", "float", "Gaussian blur sigma in pixels (0 = none)"),
    ("noise_level", "float", "Gaussian sensor-noise sigma in 8-bit units (0 = none)"),
    ("illumination_profile", "json", "Illumination gradient description"),
    ("white_balance_profile", "json", "Per-channel gains {r,g,b}"),
    ("rotation_degrees", "float", "In-plane rotation, degrees (positive = clockwise on screen, y-down axes)"),
    ("perspective_strength", "float", "Max corner jitter as a fraction of image size"),
    ("image_width", "int", "Pixels"),
    ("image_height", "int", "Pixels"),
    ("dataset_type", "str", "Always 'synthetic'"),
    # ---- extended columns
    ("variant_index", "int", "0 = clean, 1.. = augmented variant order in the config"),
    ("generation_batch", "int", "0 for the first generation run, incremented by --append"),
    ("generation_attempt", "int", "Attempt number that produced this image (re-draws after failed checks)"),
    ("scale_factor", "float", "Geometric scale"),
    ("translate_x_px", "float", "Horizontal translation, pixels"),
    ("translate_y_px", "float", "Vertical translation, pixels"),
    ("defocus_radius_px", "float", "Disk defocus radius (0 = none)"),
    ("shadow_profile", "json", "Soft-shadow description or {type: none}"),
    ("print_profile", "json", "Print/paper variation parameters"),
    ("print_delta_e", "float", "CIE76 offset of the printed spot color from the mapped color"),
    ("apparent_delta_e_vs_clean", "float", "CIE76 distance between this image's ROI median Lab and its clean image's"),
    ("spot_corners_xy", "json", "Ground-truth spot corners [[x,y] x4] TL,TR,BR,BL. Training/debug ONLY - not for inference"),
    ("mapping_id", "str", "Color-mapping identifier used to create the spot color"),
    ("image_sha256", "str", "SHA-256 of the PNG file bytes"),
    ("generator_version", "str", "Generator package version"),
]

MANIFEST_COLUMNS = [c for c, _, _ in SCHEMA]
REQUIRED_COLUMNS = MANIFEST_COLUMNS[:18]


def read_manifest(dataset_dir: str | Path) -> pd.DataFrame:
    path = Path(dataset_dir) / MANIFEST_NAME
    return pd.read_csv(path, dtype={"image_id": str, "base_sample_id": str, "relative_image_path": str},
                       keep_default_na=False, na_values=[""])


def write_manifest(df: pd.DataFrame, dataset_dir: str | Path) -> Path:
    """Atomically write the manifest (temp file + replace) with the fixed column order."""
    path = Path(dataset_dir) / MANIFEST_NAME
    tmp = path.with_suffix(".csv.tmp")
    df[MANIFEST_COLUMNS].to_csv(tmp, index=False, float_format="%.6g", lineterminator="\n")
    os.replace(tmp, path)
    return path


def schema_markdown() -> str:
    lines = ["| column | type | description |", "|---|---|---|"]
    lines += [f"| `{c}` | {t} | {d} |" for c, t, d in SCHEMA]
    return "\n".join(lines)
