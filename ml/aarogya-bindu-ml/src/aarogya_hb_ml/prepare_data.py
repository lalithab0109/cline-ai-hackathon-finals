"""Stage 1: validate dataset, build leakage-safe splits, preprocess every image, extract features.

Outputs:
    data/processed/dataset_index.csv      merged manifest + file checks + split group
    data/splits/splits.csv                uid -> split
    data/processed/features.csv           features + quality + preprocessing status per image
    reports/dataset_validation.json/.md   validation checks
    reports/preprocessing/*.png           annotated ROI previews (sample + all failures)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import cv2
import numpy as np
import pandas as pd

from . import DISCLAIMER
from . import config as C
from .dataset import DatasetError, build_groups, inspect_images, load_sources, validate_dataset
from .feature_extraction import extract_features
from .preprocessing import annotate, preprocess


def stratified_group_split(groups: pd.Series, targets: pd.Series, seed: int = C.SPLIT_SEED,
                           fractions: dict = C.SPLIT_FRACTIONS, n_bins: int = 5) -> pd.Series:
    """Assign every *group* to train/val/test, stratified by the group's mean target.

    Groups are binned into target quantiles; within each bin groups are shuffled
    with a fixed seed and allotted by cumulative fractions. All images of a group
    share one split (no leakage between augmentations of a base sample or
    between pixel-identical images).
    """
    g = pd.DataFrame({"group": groups.values, "t": targets.values}).groupby("group")["t"].mean()
    bins = pd.qcut(g.rank(method="first"), q=min(n_bins, len(g)), labels=False)
    rng = np.random.default_rng(seed)
    assign = {}
    names = list(fractions)
    cum = np.cumsum([fractions[n] for n in names])
    for b in sorted(bins.unique()):
        members = np.array(sorted(g.index[bins == b]))
        rng.shuffle(members)
        cuts = np.round(cum * len(members)).astype(int)
        start = 0
        for name, end in zip(names, cuts):
            for m in members[start:end]:
                assign[m] = name
            start = end
    return groups.map(assign)


def write_validation_report(v, path_json, path_md, n_images, split_counts):
    payload = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "overall": "PASS" if v.ok else "FAIL", "n_images": n_images, "split_counts": split_counts,
               "disclaimer": DISCLAIMER, "checks": v.checks}
    path_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = ["# Dataset validation report", "", f"> {DISCLAIMER}", "",
             f"Overall: **{payload['overall']}** - {n_images} images", "",
             "| check | status | detail |", "|---|---|---|"]
    lines += [f"| {c['check']} | {c['status']} | {c['detail']} |" for c in v.checks]
    lines += ["", "## Split counts", "", "```", json.dumps(split_counts, indent=2), "```"]
    path_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


META_COLS = ["uid", "source", "image_id", "base_sample_id", "split_group", "split", C.TARGET,
             "augmentation_profile", "brightness_factor", "contrast_factor", "blur_level", "noise_level",
             "rotation_degrees", "perspective_strength", "apparent_delta_e_vs_clean"]


def run(preview_every: int = 40) -> dict:
    prev_dir = C.REPORTS_DIR / "preprocessing"
    for d in (C.PROCESSED_DIR, C.SPLITS_DIR, C.REPORTS_DIR, prev_dir):
        d.mkdir(parents=True, exist_ok=True)
    data, infos = load_sources()
    print(f"loaded {len(data)} rows from {len(infos)} source(s)")
    img_info = inspect_images(data)
    v = validate_dataset(data, img_info, infos)
    data["split_group"] = build_groups(data, img_info)
    data["split"] = stratified_group_split(data["split_group"], data[C.TARGET])
    leak = int(data.groupby("split_group")["split"].nunique().max())
    v.add("split_group_leakage", "PASS" if leak == 1 else "FAIL",
          f"{data['split_group'].nunique()} split groups from {data['group_base'].nunique()} base samples; "
          "each group in exactly one split", max_splits_per_group=leak)
    split_counts = {s: {"images": int((data["split"] == s).sum()),
                        "groups": int(data.loc[data["split"] == s, "split_group"].nunique()),
                        "target_mean": round(float(data.loc[data["split"] == s, C.TARGET].mean()), 3),
                        "target_min": round(float(data.loc[data["split"] == s, C.TARGET].min()), 3),
                        "target_max": round(float(data.loc[data["split"] == s, C.TARGET].max()), 3)}
                    for s in C.SPLIT_FRACTIONS}
    write_validation_report(v, C.REPORTS_DIR / "dataset_validation.json", C.REPORTS_DIR / "dataset_validation.md",
                            len(data), split_counts)
    if not v.ok:
        raise DatasetError("dataset validation FAILED - see reports/dataset_validation.md")
    data.merge(img_info, on="uid").to_csv(C.DATASET_CSV, index=False)
    data[["uid", "source", "image_id", "base_sample_id", "split_group", "split", C.TARGET]].to_csv(
        C.SPLITS_CSV, index=False)

    for f in prev_dir.glob("*.png"):
        f.unlink()
    rows = []
    for i, r in enumerate(data.itertuples(index=False)):
        pre = preprocess(r.abs_path)
        row = {"uid": r.uid, "pre_status": pre.status, "pre_issues": "; ".join(pre.issues),
               "detection_method": pre.detection.method if pre.detection else "",
               "detection_confidence": pre.detection.confidence if pre.detection else 0.0}
        if pre.ok:
            row.update(extract_features(pre))
        rows.append(row)
        if (not pre.ok) or i % preview_every == 0:
            vis = annotate(pre, f"{r.uid} {r.augmentation_profile} t={getattr(r, C.TARGET):.2f}")
            tag = "FAIL_" if not pre.ok else ""
            cv2.imwrite(str(prev_dir / f"{tag}{r.source}_{r.image_id}.png"), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
        if (i + 1) % 100 == 0:
            print(f"  preprocessed {i + 1}/{len(data)}")
    out = data[META_COLS].merge(pd.DataFrame(rows), on="uid")
    out.to_csv(C.FEATURES_CSV, index=False)
    by_split = out.groupby(["split", "pre_status"]).size().unstack(fill_value=0).to_dict(orient="index")
    by_prof = out.groupby(["augmentation_profile", "pre_status"]).size().unstack(fill_value=0).to_dict(orient="index")
    report = {"by_split": by_split, "by_profile": by_prof,
              "failures": out.loc[out["pre_status"] != "ok",
                                  ["uid", "split", "augmentation_profile", C.TARGET, "pre_status",
                                   "pre_issues"]].to_dict(orient="records")}
    (C.REPORTS_DIR / "preprocessing_summary.json").write_text(json.dumps(report, indent=2, default=str),
                                                              encoding="utf-8")
    print("validation:", "PASS" if v.ok else "FAIL")
    print("splits:", json.dumps(split_counts))
    print("preprocessing by profile:", json.dumps(by_prof))
    print("disclaimer:", DISCLAIMER)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate data, split, preprocess and extract features.")
    ap.add_argument("--preview-every", type=int, default=40, help="save an annotated preview every N images")
    run(ap.parse_args(argv).preview_every)


if __name__ == "__main__":
    main()
