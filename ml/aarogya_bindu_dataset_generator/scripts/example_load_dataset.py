"""Example for the backend teammate: load the synthetic dataset, verify image/label
association, and extract color features from the images alone.

Usage:
    python scripts/example_load_dataset.py --dataset aarogya_synthetic_dataset [--n 12]

Dependencies: numpy, pandas, opencv-python-headless (all in requirements.txt).
The feature extractor is imported from this repository's reference
implementation (src/aarogya_synth/features.py); copy that file into the
backend if you want the identical ROI detection and features.

Nothing here trains a model or reports accuracy. Targets are generator-assigned
SIMULATED values, not measured hemoglobin concentrations.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from aarogya_synth.features import extract_features, load_rgb  # noqa: E402

TARGET = "target_hb_g_dl"


def load_manifest(root: Path) -> pd.DataFrame:
    df = pd.read_csv(root / "manifest.csv", dtype={"image_id": str, "base_sample_id": str})
    assert (df["dataset_type"] == "synthetic").all(), "expected a synthetic dataset"
    return df


def verify_association(root: Path, df: pd.DataFrame) -> None:
    """Every row -> existing, readable file with the recorded hash and size; numeric label."""
    problems = []
    for r in df.itertuples(index=False):
        p = root / r.relative_image_path
        if not p.is_file():
            problems.append(f"{r.image_id}: missing {p}")
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != r.image_sha256:
            problems.append(f"{r.image_id}: sha256 mismatch")
        if not np.isfinite(getattr(r, TARGET)):
            problems.append(f"{r.image_id}: invalid target")
    leak = df.groupby("base_sample_id")["dataset_split"].nunique()
    if (leak > 1).any():
        problems.append(f"split leakage for {list(leak[leak > 1].index)[:5]}")
    if problems:
        raise SystemExit("association check FAILED:\n" + "\n".join(problems[:20]))
    print(f"OK: {len(df)} rows, every row has an existing image (hash verified) and a numeric {TARGET}; "
          "no base sample spans two splits.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("aarogya_synthetic_dataset"))
    ap.add_argument("--n", type=int, default=12, help="images to extract features from")
    args = ap.parse_args()
    root = args.dataset

    df = load_manifest(root)
    print(df.groupby(["dataset_split", "augmentation_profile"]).size().unstack(fill_value=0), "\n")
    verify_association(root, df)

    # Development data only: never look at 'test' while developing.
    dev = df[df["dataset_split"].isin(["train", "val"])]
    sample = dev.groupby("augmentation_profile", group_keys=False).head(max(1, args.n // 4))
    rows = []
    for r in sample.itertuples(index=False):
        rgb = load_rgb(root / r.relative_image_path)  # inference input: image only
        feats = extract_features(rgb)  # spot is detected from pixels; no metadata used
        rows.append({"image_id": r.image_id, "profile": r.augmentation_profile,
                     TARGET: getattr(r, TARGET),  # label joined AFTER feature extraction
                     **{k: round(feats[k], 2) for k in ("rgb_median_r", "rgb_median_g", "rgb_median_b",
                                                        "hsv_h_circmean_deg", "lab_l_median", "lab_a_median",
                                                        "lab_b_median", "lab_l_std")}})
    table = pd.DataFrame(rows).sort_values(["profile", TARGET])
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("\nFeatures extracted from images (labels are generator-known simulated targets):")
        print(table.to_string(index=False))


if __name__ == "__main__":
    main()
