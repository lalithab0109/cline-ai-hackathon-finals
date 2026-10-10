"""Dataset quality checks.

Run: ``python -m aarogya_synth validate --dataset <dir>``

Each check yields a status: PASS, WARN (reported, does not fail) or FAIL.
Nothing is ever deleted or modified; suspicious cases are only reported.
Results are written to reports/validation_report.json and .md. The command
exits non-zero if any check FAILs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import DATASET_TYPE, DISCLAIMER
from . import colorspace as cs
from .augmentation import render_variant
from .color_mapping import build_mapping
from .features import SpotNotFoundError, detect_spot, load_rgb, polygon_iou, roi_pixels
from .generate import load_dataset_config, png_bytes
from .manifest import MANIFEST_COLUMNS, read_manifest
from .splits import SPLITS


@dataclass
class Check:
    name: str
    status: str = "PASS"
    details: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def fail(self, msg: str) -> None:
        self.status = "FAIL"
        self.details.append(msg)

    def warn(self, msg: str) -> None:
        if self.status == "PASS":
            self.status = "WARN"
        self.details.append(msg)


def _limit(items, n=10) -> str:
    items = list(items)
    return ", ".join(map(str, items[:n])) + (f" ... (+{len(items) - n} more)" if len(items) > n else "")


def check_manifest_structure(df: pd.DataFrame, cfg) -> Check:
    c = Check("manifest_structure")
    missing = [col for col in MANIFEST_COLUMNS if col not in df.columns]
    if missing:
        c.fail(f"missing columns: {missing}")
        return c
    req = MANIFEST_COLUMNS[:18]
    nulls = {col: int(df[col].isna().sum()) for col in req if df[col].isna().any()}
    if nulls:
        c.fail(f"missing values in required columns: {nulls}")
    if not (df["dataset_type"] == DATASET_TYPE).all():
        c.fail("dataset_type must be 'synthetic' for every row")
    bad_prof = set(df["augmentation_profile"]) - set(cfg.variants)
    if bad_prof:
        c.fail(f"unknown augmentation_profile values: {sorted(bad_prof)}")
    c.metrics = {"rows": len(df), "columns": len(df.columns)}
    return c


def check_duplicates_ids(df: pd.DataFrame) -> Check:
    c = Check("duplicate_ids_and_filenames")
    for col in ("image_id", "relative_image_path"):
        d = df[col][df[col].duplicated()]
        if len(d):
            c.fail(f"duplicate {col}: {_limit(d)}")
    lower = df["relative_image_path"].str.lower()
    if lower.duplicated().sum() > df["relative_image_path"].duplicated().sum():
        c.fail("filenames differing only by case (unsafe on Windows/macOS)")
    pairs = df.groupby(["base_sample_id", "augmentation_profile"]).size()
    if (pairs > 1).any():
        c.fail(f"base sample has the same profile twice: {_limit(pairs[pairs > 1].index)}")
    return c


def check_targets(df: pd.DataFrame, cfg) -> Check:
    c = Check("targets_valid_and_consistent")
    t = pd.to_numeric(df["target_hb_g_dl"], errors="coerce")
    bad = df.loc[t.isna() | ~np.isfinite(t), "image_id"]
    if len(bad):
        c.fail(f"missing/non-numeric targets: {_limit(bad)}")
    lo, hi = cfg.mapping.target_min, cfg.mapping.target_max
    out = df.loc[(t < lo) | (t > hi), "image_id"]
    if len(out):
        c.fail(f"targets outside [{lo}, {hi}]: {_limit(out)}")
    per_base = df.groupby("base_sample_id")["target_hb_g_dl"].nunique()
    if (per_base > 1).any():
        c.fail(f"base samples with inconsistent targets: {_limit(per_base[per_base > 1].index)}")
    c.metrics = {"min": float(t.min()), "max": float(t.max()), "mean": float(t.mean()), "std": float(t.std())}
    return c


def check_target_coverage(df: pd.DataFrame, cfg) -> Check:
    c = Check("target_range_and_distribution")
    base = df.drop_duplicates("base_sample_id")
    lo, hi = cfg.mapping.target_min, cfg.mapping.target_max
    nb = 7
    counts, edges = np.histogram(base["target_hb_g_dl"], bins=nb, range=(lo, hi))
    c.metrics = {"base_samples": len(base), "histogram_edges": [round(e, 3) for e in edges],
                 "histogram_counts": counts.tolist()}
    if (counts == 0).any():
        c.warn(f"empty target bins over [{lo}, {hi}]: {counts.tolist()}")
    expected = len(base) / nb
    if expected >= 5 and counts.min() < 0.5 * expected:
        c.warn(f"uneven target coverage: {counts.tolist()}")
    return c


def check_splits(df: pd.DataFrame, cfg) -> Check:
    c = Check("splits_and_leakage")
    bad = set(df["dataset_split"]) - set(SPLITS)
    if bad:
        c.fail(f"invalid split values: {sorted(bad)}")
    per_base = df.groupby("base_sample_id")["dataset_split"].nunique()
    leaked = per_base[per_base > 1].index
    if len(leaked):
        c.fail(f"LEAKAGE: base samples in more than one split: {_limit(leaked)}")
    # every base sample must have exactly the configured variants
    nvar = df.groupby("base_sample_id")["augmentation_profile"].apply(lambda s: sorted(s))
    incomplete = [b for b, v in nvar.items() if v != sorted(cfg.variants)]
    if incomplete:
        c.warn(f"base samples without the full variant set: {_limit(incomplete)}")
    base = df.drop_duplicates("base_sample_id")
    summary = {}
    for s in SPLITS:
        sub = base[base["dataset_split"] == s]["target_hb_g_dl"]
        summary[s] = {"base_samples": int(len(sub)), "images": int((df["dataset_split"] == s).sum()),
                      "target_min": float(sub.min()) if len(sub) else None,
                      "target_max": float(sub.max()) if len(sub) else None}
        if len(sub) == 0 and getattr(cfg.splits, s) > 0:
            c.fail(f"split '{s}' is empty")
    n = len(base)
    for s in SPLITS:
        frac = summary[s]["base_samples"] / n if n else 0
        if abs(frac - getattr(cfg.splits, s)) > 0.05 + 1.0 / max(n, 1):
            c.warn(f"split '{s}' fraction {frac:.3f} differs from configured {getattr(cfg.splits, s)}")
    c.metrics = summary
    return c


def check_files_and_images(df: pd.DataFrame, root: Path, cfg) -> tuple[list[Check], dict]:
    """Existence, readability, dimensions, dtype/RGB range, hashes, orphans, uniformity."""
    files = Check("image_files_exist_and_readable")
    dims = Check("image_dimensions_and_rgb_values")
    hashes = Check("manifest_hash_matches_file")
    orphans = Check("files_without_manifest_entry")
    uniform = Check("uniform_or_featureless_images")
    loaded: dict = {}
    for r in df.itertuples(index=False):
        p = root / r.relative_image_path
        if not p.is_file():
            files.fail(f"missing file for {r.image_id}: {r.relative_image_path}")
            continue
        raw = p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != r.image_sha256:
            hashes.fail(f"{r.image_id}: file content changed since generation")
        try:
            rgb = load_rgb(p)
        except OSError as exc:
            files.fail(str(exc))
            continue
        if rgb.shape != (cfg.image.height, cfg.image.width, 3):
            dims.fail(f"{r.image_id}: shape {rgb.shape}")
        if (r.image_width, r.image_height) != (rgb.shape[1], rgb.shape[0]):
            dims.fail(f"{r.image_id}: manifest size {r.image_width}x{r.image_height} != file {rgb.shape[1]}x{rgb.shape[0]}")
        if rgb.dtype != np.uint8 or rgb.min() < 0 or rgb.max() > 255:
            dims.fail(f"{r.image_id}: invalid RGB values / dtype {rgb.dtype}")
        if float(rgb.std()) < 1.0:
            uniform.fail(f"{r.image_id}: image is (nearly) uniform, std={rgb.std():.2f}")
        loaded[r.image_id] = (rgb, raw)
    images_dir = root / "images"
    listed = {Path(x).name.lower() for x in df["relative_image_path"]}
    if images_dir.is_dir():
        extra = [f.name for f in images_dir.iterdir() if f.is_file() and f.name.lower() not in listed]
        if extra:
            orphans.fail(f"{len(extra)} image file(s) not in manifest: {_limit(extra)}")
    files.metrics = {"checked": len(df), "readable": len(loaded)}
    return [files, dims, hashes, orphans, uniform], loaded


def check_duplicate_content(df: pd.DataFrame, loaded: dict, mapping) -> Check:
    """Exact duplicate pixel content (nothing is deleted - only reported).

    EXPECTED (WARN): all images in the group are deterministic clean renders AND
    the mapping yields the same 8-bit spot color for every target in the group,
    i.e. they were generated under identical effective settings. This happens
    when nearby targets quantize to the same RGB (8-bit resolution limit); such
    images carry slightly different labels, which is reported.
    SUSPICIOUS (FAIL): anything else, e.g. augmented images that collide.
    """
    c = Check("duplicate_image_content")
    pix_hash = {iid: hashlib.sha256(rgb.tobytes()).hexdigest() for iid, (rgb, _) in loaded.items()}
    d = df[df["image_id"].isin(pix_hash)].assign(pixel_hash=lambda x: x["image_id"].map(pix_hash))
    expected, suspicious = [], []
    for _, grp in d.groupby("pixel_hash"):
        if len(grp) < 2:
            continue
        targets = grp["target_hb_g_dl"].to_numpy(dtype=float)
        same_color = len({tuple(mapping.rgb8(t).tolist()) for t in targets}) == 1
        entry = {"image_ids": grp["image_id"].tolist(), "base_sample_ids": grp["base_sample_id"].tolist(),
                 "targets": targets.tolist(), "label_spread_g_dl": round(float(np.ptp(targets)), 4)}
        if (grp["augmentation_profile"] == "clean").all() and same_color:
            expected.append(entry)
        else:
            suspicious.append(entry)
    if suspicious:
        c.fail(f"{len(suspicious)} suspicious duplicate group(s): {_limit(suspicious)}")
    if expected:
        spread = max(e["label_spread_g_dl"] for e in expected)
        c.warn(f"{len(expected)} expected duplicate group(s): clean images whose targets quantize to the same "
               f"8-bit color (max label spread {spread} g/dL; 8-bit resolution limit, not an error)")
    c.metrics = {"expected_duplicate_groups": expected, "suspicious_duplicate_groups": suspicious}
    return c


def check_spot_detectable(df: pd.DataFrame, loaded: dict, cfg) -> Check:
    c = Check("spot_detectable_by_reference_detector")
    ious = []
    for r in df.itertuples(index=False):
        if r.image_id not in loaded:
            continue
        rgb = loaded[r.image_id][0]
        gt = np.asarray(json.loads(r.spot_corners_xy))
        try:
            iou = polygon_iou(detect_spot(rgb), gt, rgb.shape[:2])
        except SpotNotFoundError:
            iou = 0.0
        ious.append(iou)
        if iou < cfg.checks.min_detection_iou:
            c.fail(f"{r.image_id}: detector IoU {iou:.2f}")
    if ious:
        c.metrics = {"iou_min": float(np.min(ious)), "iou_mean": float(np.mean(ious))}
    return c


def check_clean_monotonicity(df: pd.DataFrame, loaded: dict, cfg, mapping) -> Check:
    """Clean images: measured ROI L* must be monotonic in target (ties allowed only from
    identical targets or 8-bit rounding), and spot pixels must equal the mapping RGB exactly."""
    c = Check("clean_color_mapping_monotonicity")
    clean = df[(df["augmentation_profile"] == "clean") & df["image_id"].isin(loaded)].copy()
    meas_l, exact_bad = [], []
    for r in clean.itertuples(index=False):
        rgb = loaded[r.image_id][0]
        px = roi_pixels(rgb, np.asarray(json.loads(r.spot_corners_xy)), shrink=0.15)
        expected = mapping.rgb8(r.target_hb_g_dl)
        if not (px == expected).all():
            exact_bad.append(r.image_id)
        meas_l.append(float(np.median(cs.srgb8_to_lab(px)[:, 0])))
    clean["measured_L"] = meas_l
    if exact_bad:
        c.fail(f"clean spot pixels differ from mapping color: {_limit(exact_bad)}")
    clean = clean.sort_values("target_hb_g_dl")
    sign = mapping.l_direction()
    dl = np.diff(clean["measured_L"].to_numpy()) * sign
    dt = np.diff(clean["target_hb_g_dl"].to_numpy())
    violations = int(((dl < -1e-9) & (dt > 0)).sum())
    ties = int(((np.abs(dl) <= 1e-9) & (dt > 0)).sum())
    if violations:
        c.fail(f"{violations} monotonicity violation(s) in measured clean L*")
    if ties:
        c.warn(f"{ties} adjacent distinct targets render to identical L* (8-bit quantization)")
    rho = float(pd.Series(clean["target_hb_g_dl"]).corr(clean["measured_L"], method="spearman")) if len(clean) > 2 else float("nan")
    c.metrics = {"clean_images": len(clean), "violations": violations, "ties": ties, "spearman_target_vs_L": rho}
    return c


def check_reproducibility(df: pd.DataFrame, loaded: dict, cfg, mapping, n: int, seed: int = 0) -> Check:
    """Re-render a random sample of rows from (target, profile, random_seed) and compare pixels."""
    c = Check("reproducibility_rerender")
    rows = df[df["image_id"].isin(loaded)]
    if n <= 0 or not len(rows):
        c.warn("skipped")
        return c
    # include at least one row per profile, then random others
    picks = rows.groupby("augmentation_profile", group_keys=False).head(1)
    rest = rows.drop(picks.index)
    if len(rest) and n > len(picks):
        picks = pd.concat([picks, rest.sample(min(n - len(picks), len(rest)), random_state=seed)])
    mismatched = []
    for r in picks.itertuples(index=False):
        rgb, _ = render_variant(cfg, mapping, float(r.target_hb_g_dl), r.augmentation_profile, int(r.random_seed))
        if not np.array_equal(rgb, loaded[r.image_id][0]):
            mismatched.append(r.image_id)
    if mismatched:
        c.fail(f"re-rendered pixels differ for {_limit(mismatched)} (different library versions can cause this; "
               "see library_versions in generation_config.json)")
    c.metrics = {"rows_rerendered": len(picks), "mismatched": len(mismatched)}
    return c


def check_mapping_config(raw_cfg: dict, df: pd.DataFrame, mapping) -> Check:
    c = Check("mapping_config_stored_and_consistent")
    desc = raw_cfg.get("mapping_description")
    if not desc:
        c.fail("generation_config.json has no mapping_description")
    elif desc != json.loads(json.dumps(mapping.describe())):
        c.fail("stored mapping_description differs from the mapping rebuilt from the config")
    ids = set(df["mapping_id"])
    if ids != {mapping.mapping_id}:
        c.fail(f"manifest mapping_id values {sorted(ids)} != {mapping.mapping_id}")
    if raw_cfg.get("dataset_type") != DATASET_TYPE:
        c.fail("generation_config.json does not declare dataset_type 'synthetic'")
    return c


def run_validation(dataset_dir: str | Path, rerender: int = 12) -> tuple[bool, list[Check]]:
    root = Path(dataset_dir)
    checks: list[Check] = []
    if not (root / "manifest.csv").is_file() or not (root / "generation_config.json").is_file():
        c = Check("dataset_files_present")
        c.fail("manifest.csv and/or generation_config.json missing")
        return False, [c]
    cfg, raw = load_dataset_config(root)
    mapping = build_mapping(cfg.mapping, cfg.config_dir)
    df = read_manifest(root)
    structure = check_manifest_structure(df, cfg)
    checks.append(structure)
    if structure.status == "FAIL" and structure.details[0].startswith("missing columns"):
        return False, checks
    checks += [check_duplicates_ids(df), check_targets(df, cfg), check_target_coverage(df, cfg),
               check_splits(df, cfg), check_mapping_config(raw, df, mapping)]
    file_checks, loaded = check_files_and_images(df, root, cfg)
    checks += file_checks
    checks += [check_duplicate_content(df, loaded, mapping), check_spot_detectable(df, loaded, cfg),
               check_clean_monotonicity(df, loaded, cfg, mapping),
               check_reproducibility(df, loaded, cfg, mapping, rerender)]
    ok = all(c.status != "FAIL" for c in checks)
    write_validation_report(root, ok, checks)
    return ok, checks


def write_validation_report(root: Path, ok: bool, checks: list[Check]) -> None:
    rep = root / "reports"
    rep.mkdir(exist_ok=True)
    doc = {"dataset_type": DATASET_TYPE, "overall": "PASS" if ok else "FAIL", "disclaimer": DISCLAIMER,
           "checks": [{"name": c.name, "status": c.status, "details": c.details, "metrics": c.metrics} for c in checks]}
    (rep / "validation_report.json").write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    lines = ["# Dataset validation report", "",
             f"**Overall: {doc['overall']}**  (dataset_type: synthetic)", "",
             f"> {DISCLAIMER}", "",
             "This report validates data integrity only. It contains generator-known targets and no model "
             "predictions or accuracy figures.", "",
             "| check | status | notes |", "|---|---|---|"]
    for c in checks:
        note = "; ".join(c.details)[:300].replace("|", "/") if c.details else ""
        lines.append(f"| {c.name} | {c.status} | {note} |")
    lines += ["", "## Metrics", ""]
    for c in checks:
        if c.metrics:
            lines.append(f"- **{c.name}**: `{json.dumps(c.metrics, default=str)[:600]}`")
    (rep / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
