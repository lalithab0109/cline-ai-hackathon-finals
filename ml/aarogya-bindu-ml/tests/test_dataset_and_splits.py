import json

import numpy as np
import pandas as pd
import pytest
from conftest import make_strip, save_rgb

from aarogya_hb_ml import config as C
from aarogya_hb_ml.dataset import DatasetError, build_groups, inspect_images, load_sources, validate_dataset
from aarogya_hb_ml.prepare_data import stratified_group_split

MAPPING = {"mapping_id": "m1", "type": "lab_interp", "equation": "t=clip((c-4)/14)", "target_min": 4, "target_max": 18,
           "gamma": 1.0, "lab_low": [86, 8, 38], "lab_high": [38, 45, 28]}


def _make_source(root, sid, n=4, mapping=MAPPING, targets=None, dup_last=False):
    d = root / sid
    (d / "images").mkdir(parents=True)
    rows = []
    for i in range(n):
        rgb, _ = make_strip(spot_rgb=(230, 150 - 10 * i, 110))
        if dup_last and i == n - 1:
            rgb, _ = make_strip(spot_rgb=(230, 150, 110))  # identical pixels to sample 0
        save_rgb(d / "images" / f"IMG{i}.png", rgb)
        rows.append({"image_id": f"IMG{i}", "relative_image_path": f"images/IMG{i}.png", "base_sample_id": f"B{i}",
                     C.TARGET: (targets or [5 + i for i in range(n)])[i], "augmentation_profile": "clean",
                     "dataset_type": "synthetic"})
    pd.DataFrame(rows).to_csv(d / "manifest.csv", index=False)
    (d / "generation_config.json").write_text(json.dumps({"dataset_type": "synthetic", "mapping_description": mapping}))
    return {"source_id": sid, "path": sid}


def _registry(tmp_path, sources):
    p = tmp_path / "sources.json"
    p.write_text(json.dumps({"sources": sources}))
    return p


def test_merges_compatible_contributors_with_unique_ids(tmp_path):
    reg = _registry(tmp_path, [_make_source(tmp_path, "a"), _make_source(tmp_path, "b")])
    data, infos = load_sources(reg)
    assert len(data) == 8 and data["uid"].is_unique and data["group_base"].nunique() == 8
    v = validate_dataset(data, inspect_images(data), infos)
    assert v.ok


def test_refuses_incompatible_mapping(tmp_path):
    other = dict(MAPPING, gamma=1.3)
    reg = _registry(tmp_path, [_make_source(tmp_path, "a"), _make_source(tmp_path, "b", mapping=other)])
    with pytest.raises(DatasetError, match="different color-to-target mapping"):
        load_sources(reg)


def test_missing_manifest_column_and_files(tmp_path):
    s = _make_source(tmp_path, "a")
    df = pd.read_csv(tmp_path / "a" / "manifest.csv").drop(columns=["base_sample_id"])
    df.to_csv(tmp_path / "a" / "manifest.csv", index=False)
    with pytest.raises(DatasetError, match="required columns"):
        load_sources(_registry(tmp_path, [s]))


def test_validation_flags_missing_image_and_bad_target(tmp_path):
    reg = _registry(tmp_path, [_make_source(tmp_path, "a", targets=[5, 6, 25, 7])])
    data, infos = load_sources(reg)
    (tmp_path / "a" / "images" / "IMG0.png").unlink()
    v = validate_dataset(data, inspect_images(data), infos)
    status = {c["check"]: c["status"] for c in v.checks}
    assert not v.ok
    assert status["files_exist_and_readable"] == "FAIL" and status["target_within_documented_range"] == "FAIL"


def test_identical_images_are_grouped_together(tmp_path):
    reg = _registry(tmp_path, [_make_source(tmp_path, "a", dup_last=True, targets=[5.0, 6, 7, 5.05])])
    data, infos = load_sources(reg)
    info = inspect_images(data)
    groups = build_groups(data, info)
    assert groups.iloc[0] == groups.iloc[3] and groups.nunique() == 3
    v = validate_dataset(data, info, infos)
    assert {c["check"]: c["status"] for c in v.checks}["duplicate_images_and_conflicting_labels"] == "WARN"


def test_group_split_has_no_leakage_and_is_deterministic():
    groups = pd.Series([f"g{i // 4}" for i in range(400)])
    targets = pd.Series(np.repeat(np.linspace(4, 18, 100), 4))
    s1 = stratified_group_split(groups, targets, seed=1)
    s2 = stratified_group_split(groups, targets, seed=1)
    assert (s1 == s2).all()
    assert pd.DataFrame({"g": groups, "s": s1}).groupby("g")["s"].nunique().max() == 1
    frac = s1.value_counts(normalize=True)
    assert abs(frac["train"] - 0.7) < 0.05 and abs(frac["test"] - 0.15) < 0.05


@pytest.mark.skipif(not C.SPLITS_CSV.is_file(), reason="pipeline not run")
def test_real_splits_have_no_group_or_pixel_leakage():
    s = pd.read_csv(C.SPLITS_CSV)
    assert s.groupby("split_group")["split"].nunique().max() == 1
    assert s.groupby("base_sample_id")["split"].nunique().max() == 1
    idx = pd.read_csv(C.DATASET_CSV)
    assert idx.groupby("pixel_hash")["split"].nunique().max() == 1
