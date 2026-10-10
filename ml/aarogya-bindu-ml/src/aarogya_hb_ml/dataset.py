"""Dataset loading, contributor compatibility checks and validation.

Every contributor ("source") is a folder with ``manifest.csv``,
``generation_config.json`` and ``images/``, registered in ``data/sources.json``.

Merging rules (no silent merges):
    * every source must declare ``dataset_type == synthetic``
    * every source's ``mapping_description`` (equation + parameters) must be
      identical to the first source's; otherwise loading stops with an error
      listing the differing keys
    * required columns must be present; labels come ONLY from ``target_hb_g_dl``
      in the manifest (never from filenames)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

REQUIRED_COLUMNS = ["image_id", "relative_image_path", "base_sample_id", C.TARGET]
OPTIONAL_METADATA = ["augmentation_profile", "brightness_factor", "contrast_factor", "blur_level",
                     "noise_level", "rotation_degrees", "perspective_strength",
                     "apparent_delta_e_vs_clean", "image_sha256", "dataset_type", "mapping_id"]


class DatasetError(RuntimeError):
    """Raised when data are missing or contributor datasets are incompatible."""


@dataclass
class SourceInfo:
    source_id: str
    root: Path
    mapping: dict
    config_hash: str | None
    n_rows: int


@dataclass
class ValidationResult:
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "", **metrics) -> None:
        self.checks.append({"check": name, "status": status, "detail": detail, "metrics": metrics})

    @property
    def ok(self) -> bool:
        return all(c["status"] != "FAIL" for c in self.checks)


def _mapping_signature(mapping: dict) -> dict:
    """The parts of a mapping description that define the color-to-target equation."""
    keys = ("type", "equation", "target_min", "target_max", "gamma", "lab_low", "lab_high",
            "color_space", "targets", "labs")
    return {k: mapping.get(k) for k in keys if k in mapping}


def load_sources(sources_file: Path = C.SOURCES_FILE) -> tuple[pd.DataFrame, list[SourceInfo]]:
    """Load and merge all registered sources after verifying mapping compatibility."""
    if not sources_file.is_file():
        raise DatasetError(f"missing source registry {sources_file}")
    reg = json.loads(sources_file.read_text(encoding="utf-8"))
    frames, infos = [], []
    for s in reg.get("sources", []):
        root = (sources_file.parent / s["path"]).resolve()
        man, cfg = root / s.get("manifest", "manifest.csv"), root / s.get("config", "generation_config.json")
        missing = [p.name for p in (man, cfg) if not p.is_file()]
        if missing:
            raise DatasetError(f"source '{s['source_id']}' at {root} is missing {missing}. Required: manifest.csv "
                               "(with image_id, relative_image_path, base_sample_id, target_hb_g_dl) and "
                               "generation_config.json (with mapping_description).")
        gen = json.loads(cfg.read_text(encoding="utf-8"))
        if gen.get("dataset_type") != "synthetic":
            raise DatasetError(f"source '{s['source_id']}' does not declare dataset_type 'synthetic'")
        mapping = gen.get("mapping_description")
        if not mapping:
            raise DatasetError(f"source '{s['source_id']}' has no mapping_description; cannot verify the "
                               "color-to-target equation, refusing to merge")
        df = pd.read_csv(man, dtype={"image_id": str, "base_sample_id": str}, keep_default_na=False,
                         na_values=[""])
        absent = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if absent:
            raise DatasetError(f"source '{s['source_id']}' manifest lacks required columns {absent}")
        df.insert(0, "source", s["source_id"])
        df["abs_path"] = [str(root / p) for p in df["relative_image_path"]]
        # globally unique ids even if two contributors both used IMG000001 / B000001
        df["uid"] = df["source"] + ":" + df["image_id"].astype(str)
        df["group_base"] = df["source"] + ":" + df["base_sample_id"].astype(str)
        frames.append(df)
        infos.append(SourceInfo(s["source_id"], root, mapping, gen.get("config_hash"), len(df)))
    if not frames:
        raise DatasetError("no sources registered in data/sources.json")
    ref = _mapping_signature(infos[0].mapping)
    for info in infos[1:]:
        sig = _mapping_signature(info.mapping)
        if sig != ref:
            diff = sorted(k for k in set(ref) | set(sig) if ref.get(k) != sig.get(k))
            raise DatasetError(
                f"source '{info.source_id}' uses a different color-to-target mapping than "
                f"'{infos[0].source_id}' (differs in {diff}); refusing to merge. Train separately or "
                "regenerate with the same mapping.")
    data = pd.concat(frames, ignore_index=True)
    for col in OPTIONAL_METADATA:
        if col not in data.columns:
            data[col] = np.nan
    return data, infos


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_images(data: pd.DataFrame) -> pd.DataFrame:
    """Per-image file checks: file_exists, readable, width, height, channels, sha256_ok, pixel_hash."""
    from .preprocessing import ImageLoadError, load_image_rgb

    rows = []
    for r in data.itertuples(index=False):
        rec = {"uid": r.uid, "file_exists": Path(r.abs_path).is_file(), "readable": False, "width": None,
               "height": None, "channels": None, "sha256_ok": None, "pixel_hash": None, "load_error": ""}
        if rec["file_exists"]:
            raw = Path(r.abs_path).read_bytes()
            expected = getattr(r, "image_sha256", None)
            if isinstance(expected, str) and expected:
                rec["sha256_ok"] = hashlib.sha256(raw).hexdigest() == expected
            try:
                img = load_image_rgb(r.abs_path)
                rec.update(readable=True, height=img.shape[0], width=img.shape[1], channels=img.shape[2],
                           pixel_hash=hashlib.sha256(img.tobytes()).hexdigest())
            except ImageLoadError as exc:
                rec["load_error"] = str(exc)
        rows.append(rec)
    return pd.DataFrame(rows)


def build_groups(data: pd.DataFrame, img_info: pd.DataFrame) -> pd.Series:
    """Leakage-safe group id per image.

    Starts from ``source:base_sample_id``. Images with identical pixels in
    different base samples (e.g. clean images whose targets quantize to the same
    8-bit color) are united with union-find, so identical images can never be
    split across train/val/test.
    """
    parent = {g: g for g in data["group_base"].unique()}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    merged = data[["uid", "group_base"]].merge(img_info[["uid", "pixel_hash"]], on="uid")
    for _, grp in merged.dropna(subset=["pixel_hash"]).groupby("pixel_hash"):
        bases = grp["group_base"].unique()
        for b in bases[1:]:
            ra, rb = find(bases[0]), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    return data["group_base"].map(find)


def validate_dataset(data: pd.DataFrame, img_info: pd.DataFrame, infos: list[SourceInfo]) -> ValidationResult:
    v = ValidationResult()
    lo, hi = C.DOCUMENTED_TARGET_RANGE
    m = data.merge(img_info, on="uid")

    v.add("sources_and_mapping", "PASS",
          f"{len(infos)} source(s) {[i.source_id for i in infos]}; identical mapping "
          f"'{infos[0].mapping.get('mapping_id')}'", n_sources=len(infos),
          equation=infos[0].mapping.get("equation"))
    if len(infos) == 1:
        v.add("second_contributor", "WARN", "only one contributor dataset found; per-contributor "
              "comparison covers a single source")

    missing = m.loc[~m["file_exists"], "uid"].tolist()
    unreadable = m.loc[m["file_exists"] & ~m["readable"], "uid"].tolist()
    v.add("files_exist_and_readable", "FAIL" if missing or unreadable else "PASS",
          f"missing={missing[:10]} unreadable={unreadable[:10]}", missing=len(missing), unreadable=len(unreadable))
    rd = m[m["readable"]]
    bad_dim = rd.loc[(rd["width"] != C.EXPECTED_SIZE[0]) | (rd["height"] != C.EXPECTED_SIZE[1])
                     | (rd["channels"] != 3), "uid"].tolist()
    v.add("rgb_dimensions_512x512", "FAIL" if bad_dim else "PASS", f"bad={bad_dim[:10]}", bad=len(bad_dim))
    sha_bad = m.loc[m["sha256_ok"].eq(False), "uid"].tolist()
    v.add("file_hash_matches_manifest", "FAIL" if sha_bad else "PASS", f"mismatched={sha_bad[:10]}")

    t = pd.to_numeric(data[C.TARGET], errors="coerce")
    invalid = data.loc[~np.isfinite(t.to_numpy(dtype=float)), "uid"].tolist()
    v.add("target_finite_numeric", "FAIL" if invalid else "PASS", f"invalid={invalid[:10]}", invalid=len(invalid))
    out = data.loc[(t < lo) | (t > hi), "uid"].tolist()
    v.add("target_within_documented_range", "FAIL" if out else "PASS",
          f"documented range [{lo}, {hi}] g/dL", outside=len(out), min=float(t.min()), max=float(t.max()))

    dup_ids = data.loc[data["uid"].duplicated(), "uid"].tolist()
    dup_paths = data.loc[data["abs_path"].str.lower().duplicated(), "abs_path"].tolist()
    v.add("duplicate_ids_and_paths", "FAIL" if dup_ids or dup_paths else "PASS",
          f"dup_ids={dup_ids[:5]} dup_paths={dup_paths[:5]}")
    per_base = data.groupby("group_base")[C.TARGET].nunique()
    conflict = per_base[per_base > 1].index.tolist()
    v.add("consistent_label_per_base_sample", "FAIL" if conflict else "PASS", f"conflicting={conflict[:10]}")

    groups, max_spread = [], 0.0
    for _, grp in m.dropna(subset=["pixel_hash"]).groupby("pixel_hash"):
        if len(grp) > 1:
            spread = float(grp[C.TARGET].max() - grp[C.TARGET].min())
            max_spread = max(max_spread, spread)
            groups.append({"uids": grp["uid"].tolist(), "targets": grp[C.TARGET].tolist(), "spread": round(spread, 3)})
    status = "PASS" if not groups else ("FAIL" if max_spread > 0.25 else "WARN")
    detail = (f"{len(groups)} identical-pixel group(s), max label spread {max_spread:.2f} g/dL "
              "(8-bit quantization); united into one split group" if groups else "no identical images")
    v.add("duplicate_images_and_conflicting_labels", status, detail, groups=len(groups),
          max_label_spread=round(max_spread, 3), examples=groups[:10])

    v.add("grouping_metadata", "PASS" if data["base_sample_id"].notna().all() else "FAIL",
          f"{data['group_base'].nunique()} base samples; profiles "
          f"{sorted(data['augmentation_profile'].dropna().astype(str).unique().tolist())}")
    dist = data.groupby("source")[C.TARGET].describe().round(3)
    v.add("contributor_distributions", "PASS", "per-source target statistics",
          table=json.loads(dist.to_json(orient="index")))
    not_syn = data["dataset_type"].notna() & (data["dataset_type"] != "synthetic")
    v.add("dataset_type_synthetic", "FAIL" if not_syn.any() else "PASS",
          "all rows marked synthetic" if not not_syn.any() else "non-synthetic rows present")
    return v
