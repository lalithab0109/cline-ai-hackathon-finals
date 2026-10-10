"""Writes the dataset card (README.md) inside each generated dataset folder."""

from __future__ import annotations

import json
from pathlib import Path

from . import DISCLAIMER
from .manifest import read_manifest, schema_markdown


def write_dataset_readme(dataset_dir: str | Path) -> Path:
    root = Path(dataset_dir)
    raw = json.loads((root / "generation_config.json").read_text(encoding="utf-8"))
    df = read_manifest(root)
    m = raw["mapping_description"]
    im = raw["image"]
    split_counts = df.drop_duplicates("base_sample_id")["dataset_split"].value_counts().to_dict()
    text = f"""# Aarogya Bindu SYNTHETIC hemoglobin-assay image dataset

> **{DISCLAIMER}**

- dataset_type: **synthetic**
- images: {len(df)} | base samples: {df['base_sample_id'].nunique()} | variants: {', '.join(raw['variants'])}
- base samples per split: {split_counts}
- generator version: {raw['generator_version']} | config hash: `{raw['config_hash']}`
- generation batches: {len(raw['batches'])} (seeds per batch are listed in `generation_config.json`)

## Contents

| path | description |
|---|---|
| `images/sample_NNNNNN.png` | {im['width']}x{im['height']} 8-bit RGB PNG; opaque filenames (no labels) |
| `manifest.csv` | one row per image; label column `target_hb_g_dl` |
| `generation_config.json` | full resolved configuration, mapping description, library versions, batch seeds |
| `previews/preview_grid.png` | low / middle / high targets x clean / mild / moderate / challenging |
| `reports/` | validation report, mapping curve, split distributions, augmentation summary |

## Image geometry

Coordinate convention: {raw['coordinate_convention']}.
Clean spot: x={im['spot_x']}, y={im['spot_y']}, width={im['spot_width']}, height={im['spot_height']} on a
white background {im['background_rgb']}. Augmented images move/rotate/warp the spot; the true corners are in
`spot_corners_xy` (for debugging/evaluation only - an inference pipeline must locate the spot itself).

## Synthetic color mapping (NOT a clinical calibration)

`{m['mapping_id']}` - {m.get('equation', '')}

```json
{json.dumps(m, indent=2)}
```

## Splits

Splits are assigned per **base sample** (stratified by target, seeded by `split_seed`) before augmentation;
all images of a base sample share its split. Keep `test` untouched during model development.
A random synthetic test split does NOT demonstrate clinical validity or generalization to real assays.

## Manifest schema

{schema_markdown()}

See the generator project's README for usage, feature-extraction guidance and limitations.
"""
    out = root / "README.md"
    out.write_text(text, encoding="utf-8")
    return out
