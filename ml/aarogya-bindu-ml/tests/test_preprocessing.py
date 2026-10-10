import numpy as np
import pytest
from conftest import make_strip, save_rgb

from aarogya_hb_ml.feature_extraction import FEATURE_SETS, extract_features
from aarogya_hb_ml.preprocessing import ImageLoadError, load_image_rgb, order_corners, preprocess


def _corner_err(det, box):
    return np.abs(np.sort(det.corners, axis=0) - np.sort(box.astype(float), axis=0)).max()


def test_detects_axis_aligned_spot():
    rgb, box = make_strip()
    pre = preprocess(rgb)
    assert pre.ok, pre.issues
    assert _corner_err(pre.detection, box) < 3.0


@pytest.mark.parametrize("angle", [-25, 10, 33])
def test_detects_rotated_spot_and_rectifies_landscape(angle):
    rgb, box = make_strip(angle=angle)
    pre = preprocess(rgb)
    assert pre.ok, pre.issues
    assert pre.patch.shape[1] > pre.patch.shape[0]
    # interior ROI should contain only spot color
    assert np.abs(np.median(pre.roi_pixels, axis=0) - np.array([230, 150, 110])).max() <= 3


def test_detection_not_tied_to_fixed_coordinates():
    rgb, box = make_strip(center=(150, 360), wh=(120, 90))
    pre = preprocess(rgb)
    assert pre.ok and _corner_err(pre.detection, box) < 3.0


def test_blank_image_fails_with_reason():
    pre = preprocess(np.full((512, 512, 3), 240, np.uint8))
    assert not pre.ok and pre.status == "detection_failed"
    assert "no plausible reaction rectangle" in pre.issues[0]


def test_heavy_blur_is_rejected_or_detection_fails():
    rgb, _ = make_strip(blur=25)
    pre = preprocess(rgb)
    assert not pre.ok


def test_overexposure_is_flagged():
    rgb, _ = make_strip(spot_rgb=(250, 240, 200), brightness=1.6)
    pre = preprocess(rgb)
    assert not pre.ok
    assert any("overexposed" in i or "no plausible" in i for i in pre.issues)


def test_dark_background_is_flagged():
    rgb, _ = make_strip(paper=(60, 60, 60), spot_rgb=(80, 30, 20))
    pre = preprocess(rgb)
    assert not pre.ok


def test_corrupt_and_missing_files(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image at all")
    with pytest.raises(ImageLoadError):
        load_image_rgb(bad)
    with pytest.raises(ImageLoadError):
        load_image_rgb(tmp_path / "missing.png")
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    assert preprocess(empty).status == "load_failed"


def test_wrong_size_rejected(tmp_path):
    rgb, _ = make_strip(size=300, center=(150, 150), wh=(100, 70))
    p = save_rgb(tmp_path / "small.png", rgb)
    pre = preprocess(p)
    assert pre.status == "load_failed" and "expected" in pre.issues[0]
    assert preprocess(p, expected_size=None).ok


def test_order_corners_landscape():
    pts = np.array([[10, 10], [10, 110], [60, 110], [60, 10]], float)  # portrait 50x100
    o = order_corners(pts)
    assert np.linalg.norm(o[1] - o[0]) >= np.linalg.norm(o[3] - o[0])


def test_white_normalization_cancels_global_brightness():
    a = extract_features(preprocess(make_strip(brightness=1.0)[0]))
    b = extract_features(preprocess(make_strip(brightness=0.8)[0]))
    assert abs(a["raw_g"] - b["raw_g"]) > 0.05  # raw color moves
    for k in ("norm_r", "norm_g", "norm_b"):
        assert abs(a[k] - b[k]) < 0.02  # normalized color nearly invariant


def test_features_finite_and_complete():
    f = extract_features(preprocess(make_strip(noise=4, seed=3)[0]))
    for cols in FEATURE_SETS.values():
        assert all(np.isfinite(f[c]) for c in cols)
    assert -1 <= f["norm_hue_sin"] <= 1 and abs(f["norm_hue_sin"] ** 2 + f["norm_hue_cos"] ** 2 - 1) < 1e-6
