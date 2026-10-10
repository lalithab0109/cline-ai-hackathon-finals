"""Dataset generation: targets -> splits -> clean + augmented images -> manifest.

Order of operations for one batch (guarantees leakage-free splits):
    1. draw base-sample targets (generation_seed, stratified-uniform)
    2. assign base samples to train/val/test (split_seed)       <- before augmentation
    3. render clean image + each augmented variant per base sample
    4. per-image checks; failed variants are re-drawn with attempt+1 (new derived
       seed) up to checks.max_attempts, otherwise generation stops with an error
    5. images written to a staging folder, moved into images/ only after the
       whole batch succeeded; then manifest.csv and generation_config.json are
       written atomically

Existing data is never overwritten: a non-empty output folder requires
``--append`` (with an identical core configuration), and image files are opened
in exclusive-create mode.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image

from . import DATASET_TYPE, DISCLAIMER, __version__
from . import colorspace as cs
from .augmentation import render_variant
from .color_mapping import build_mapping
from .config import ConfigError, GeneratorConfig, config_from_dict
from .features import SpotNotFoundError, detect_spot, paper_pixels, polygon_iou, roi_pixels
from .manifest import CONFIG_NAME, MANIFEST_COLUMNS, MANIFEST_NAME, read_manifest, write_manifest
from .seeding import image_seed, target_rng
from .splits import assign_splits

log = logging.getLogger("aarogya_synth")

COORDINATE_CONVENTION = (
    "origin (0,0) = top-left; x to the right (columns), y downward (rows); pixel (i,j) covers "
    "[i,i+1)x[j,j+1); clean spot covers columns spot_x..spot_x+spot_width-1, rows spot_y..spot_y+spot_height-1; "
    "spot_corners_xy are continuous coordinates ordered TL,TR,BR,BL"
)


class GenerationError(RuntimeError):
    pass


def library_versions() -> dict[str, str]:
    import matplotlib
    import PIL

    return {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
            "pillow": PIL.__version__, "pandas": pd.__version__, "matplotlib": matplotlib.__version__}


def sample_targets(cfg: GeneratorConfig, n: int, batch_index: int) -> np.ndarray:
    """Stratified-uniform targets: one jittered draw per equal-width bin, then shuffled.

    Shuffling means base_sample_id order carries no information about the target.
    """
    rng = target_rng(cfg.generation_seed, batch_index)
    lo, hi = cfg.mapping.target_min, cfg.mapping.target_max
    edges = np.linspace(lo, hi, n + 1)
    t = edges[:-1] + rng.random(n) * (edges[1:] - edges[:-1])
    rng.shuffle(t)
    return np.clip(np.round(t, cfg.target_decimals), lo, hi)


def png_bytes(rgb: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def roi_median_lab(rgb: np.ndarray, corners: np.ndarray) -> np.ndarray:
    return np.median(cs.srgb8_to_lab(roi_pixels(rgb, corners, shrink=0.15)), axis=0)


def check_image(cfg: GeneratorConfig, rgb: np.ndarray, corners: np.ndarray) -> list[str]:
    """Per-image generation checks. Returns a list of problems (empty = OK)."""
    problems = []
    im = cfg.image
    if rgb.dtype != np.uint8 or rgb.shape != (im.height, im.width, 3):
        problems.append(f"bad array {rgb.dtype} {rgb.shape}")
        return problems
    if float(rgb.std()) < 1.0:
        problems.append("image nearly uniform")
    c = np.asarray(corners)
    m = cfg.checks.min_margin_px
    if c[:, 0].min() < m or c[:, 1].min() < m or c[:, 0].max() > im.width - m or c[:, 1].max() > im.height - m:
        problems.append("spot too close to the image border")
    spot_lab = roi_median_lab(rgb, c)
    paper = paper_pixels(rgb, c)
    if len(paper):
        paper_lab = np.median(cs.srgb8_to_lab(paper), axis=0)
        de = float(cs.delta_e76(spot_lab, paper_lab))
        if de < cfg.checks.min_spot_paper_delta_e:
            problems.append(f"spot/paper contrast too low (dE={de:.1f})")
    if cfg.checks.require_detectable_spot:
        try:
            iou = polygon_iou(detect_spot(rgb), c, rgb.shape[:2])
            if iou < cfg.checks.min_detection_iou:
                problems.append(f"reference detector IoU {iou:.2f} < {cfg.checks.min_detection_iou}")
        except SpotNotFoundError as exc:
            problems.append(f"reference detector failed: {exc}")
    return problems


def _prepare_output(cfg: GeneratorConfig, out: Path, append: bool):
    """Return (batch_index, next_base_index, next_image_index, existing_config, existing_manifest)."""
    has_content = out.exists() and any(not p.name.startswith(".staging") for p in out.iterdir())
    if not has_content:
        if append:
            log.info("--append given but %s is empty; creating a new dataset", out)
        return 0, 1, 1, None, None
    if not append:
        raise GenerationError(
            f"output folder {out} is not empty. Use --append to add samples, or choose a new --output "
            "folder. Existing data is never overwritten."
        )
    cfg_path, man_path = out / CONFIG_NAME, out / MANIFEST_NAME
    if not cfg_path.is_file() or not man_path.is_file():
        raise GenerationError(f"{out} has content but no {CONFIG_NAME}/{MANIFEST_NAME}; refusing to append")
    existing = json.loads(cfg_path.read_text(encoding="utf-8"))
    if existing.get("config_hash") != cfg.core_hash():
        raise GenerationError(
            "core configuration (image, mapping, profiles, variants, splits, checks) differs from the "
            f"existing dataset (existing {existing.get('config_hash')}, new {cfg.core_hash()}); refusing to "
            "append. Re-run with --config <dataset>/generation_config.json."
        )
    df = read_manifest(out)
    if not len(df):
        raise GenerationError("existing manifest is empty; refusing to append")
    batch = int(df["generation_batch"].max()) + 1
    next_base = int(df["base_sample_id"].str[1:].astype(int).max()) + 1
    next_img = int(df["image_id"].str[3:].astype(int).max()) + 1
    return batch, next_base, next_img, existing, df


def _render_checked(cfg, mapping, target, variant, vi, batch, base_index):
    """Render one variant, re-drawing with attempt+1 (new derived seed) when checks fail."""
    max_attempts = 1 if variant == "clean" else cfg.checks.max_attempts
    history = []
    for attempt in range(max_attempts):
        seed = image_seed(cfg.generation_seed, batch, base_index, vi, attempt)
        try:
            rgb, params = render_variant(cfg, mapping, target, variant, seed)
            problems = check_image(cfg, rgb, params["spot_corners_xy"])
        except (RuntimeError, SpotNotFoundError) as exc:
            problems = [str(exc)]
        if not problems:
            return rgb, params, seed, attempt, history
        history.append({"attempt": attempt, "seed": seed, "problems": problems})
        log.warning("B%06d %s attempt %d failed checks: %s", base_index, variant, attempt, problems)
    raise GenerationError(
        f"base sample B{base_index:06d} variant '{variant}' failed checks after {max_attempts} "
        f"attempt(s): {history}. Adjust profile ranges or checks in the config."
    )


def _manifest_row(cfg, mapping, params, data, rel, img_index, base_index, target, split, seed,
                  variant, vi, batch, attempt, corners, apparent_de) -> dict:
    return {
        **{k: v for k, v in params.items() if k != "spot_corners_xy"},
        "image_id": f"IMG{img_index:06d}", "relative_image_path": rel,
        "base_sample_id": f"B{base_index:06d}", "target_hb_g_dl": target,
        "dataset_split": split, "random_seed": seed, "augmentation_profile": variant,
        "image_width": cfg.image.width, "image_height": cfg.image.height,
        "dataset_type": DATASET_TYPE, "variant_index": vi, "generation_batch": batch,
        "generation_attempt": attempt, "apparent_delta_e_vs_clean": round(apparent_de, 4),
        "spot_corners_xy": json.dumps(np.round(corners, 3).tolist(), separators=(",", ":")),
        "mapping_id": mapping.mapping_id, "image_sha256": hashlib.sha256(data).hexdigest(),
        "generator_version": __version__,
    }


def generate_dataset(cfg: GeneratorConfig, out_dir: str | Path, append: bool = False) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mapping = build_mapping(cfg.mapping, cfg.config_dir)
    batch, next_base, next_img, existing_cfg, existing_df = _prepare_output(cfg, out, append)
    n = cfg.num_base_samples
    log.info("batch %d: %d base samples x %d variants -> %s", batch, n, len(cfg.variants), out)

    targets = sample_targets(cfg, n, batch)
    existing_counts = None
    if existing_df is not None:
        existing_counts = existing_df.drop_duplicates("base_sample_id")["dataset_split"].value_counts().to_dict()
    splits = assign_splits(targets, cfg.splits, cfg.split_seed, batch, existing_counts)  # BEFORE augmentation

    staging = out / f".staging_batch{batch}"
    shutil.rmtree(staging, ignore_errors=True)  # leftovers of an interrupted run (never images/)
    staging.mkdir()
    rows, regen_log, img_index = [], [], next_img
    try:
        for k in range(n):
            base_index, target, clean_lab = next_base + k, float(targets[k]), None
            for vi, variant in enumerate(cfg.variants):
                rgb, params, seed, attempt, hist = _render_checked(cfg, mapping, target, variant, vi, batch, base_index)
                regen_log += [{"base_sample_id": f"B{base_index:06d}", "variant": variant, **h} for h in hist]
                corners = np.asarray(params["spot_corners_xy"])
                med = roi_median_lab(rgb, corners)
                clean_lab = med if variant == "clean" else clean_lab
                data = png_bytes(rgb)
                rel = f"images/sample_{img_index:06d}.png"
                (staging / Path(rel).name).write_bytes(data)
                rows.append(_manifest_row(cfg, mapping, params, data, rel, img_index, base_index, target,
                                          splits[k], seed, variant, vi, batch, attempt, corners,
                                          float(cs.delta_e76(med, clean_lab))))
                img_index += 1
            if (k + 1) % 25 == 0 or k + 1 == n:
                log.info("  rendered %d/%d base samples", k + 1, n)
        images_dir = out / "images"
        images_dir.mkdir(exist_ok=True)
        clashes = [r["relative_image_path"] for r in rows if (out / r["relative_image_path"]).exists()]
        if clashes:
            raise GenerationError(f"refusing to overwrite existing files, e.g. {clashes[:3]}")
        for r in rows:
            (staging / Path(r["relative_image_path"]).name).replace(out / r["relative_image_path"])
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    new_df = pd.DataFrame(rows)[MANIFEST_COLUMNS]
    df = new_df if existing_df is None else pd.concat([existing_df[MANIFEST_COLUMNS], new_df], ignore_index=True)
    write_manifest(df, out)
    batch_info = {
        "batch_index": batch, "generation_seed": cfg.generation_seed, "split_seed": cfg.split_seed,
        "num_base_samples": n, "num_images": len(new_df),
        "first_base_sample_id": f"B{next_base:06d}", "last_base_sample_id": f"B{next_base + n - 1:06d}",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "regenerations": regen_log,
    }
    write_generation_config(cfg, mapping, out, (existing_cfg or {}).get("batches", []) + [batch_info])
    (out / "reports").mkdir(exist_ok=True)
    pd.DataFrame(mapping.table()).to_csv(out / "reports" / "color_mapping_table.csv", index=False)
    log.info("batch %d done: %d new images (%d total), %d regeneration(s)", batch, len(new_df), len(df), len(regen_log))
    return batch_info


def write_generation_config(cfg: GeneratorConfig, mapping, out: Path, batches: list[dict]) -> None:
    doc = {
        "_comment": "Resolved configuration of a SYNTHETIC dataset. Reusable as --config together with --append.",
        "dataset_type": DATASET_TYPE, "disclaimer": DISCLAIMER, "generator_version": __version__,
        "config_hash": cfg.core_hash(), "coordinate_convention": COORDINATE_CONVENTION,
        "mapping_description": mapping.describe(), "library_versions": library_versions(),
        **cfg.to_dict(),
        "batches": batches,
    }
    # top-level seeds/num_base_samples reflect the most recent batch; per-batch values are in "batches"
    tmp = out / (CONFIG_NAME + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    tmp.replace(out / CONFIG_NAME)


def load_dataset_config(dataset_dir: str | Path) -> tuple[GeneratorConfig, dict]:
    """Rebuild the GeneratorConfig stored in a dataset's generation_config.json."""
    raw = json.loads((Path(dataset_dir) / CONFIG_NAME).read_text(encoding="utf-8"))
    cfg = config_from_dict(raw, config_dir=None)
    if cfg.core_hash() != raw.get("config_hash"):
        raise ConfigError("generation_config.json hash mismatch (edited file or different generator version)")
    return cfg, raw
