import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def make_strip(spot_rgb=(230, 150, 110), paper=(245, 245, 240), size=512, center=(256, 256), wh=(160, 110),
               angle=0.0, brightness=1.0, blur=0.0, noise=0.0, seed=0):
    """Synthetic test image: paper + one rotated colored rectangle (independent of the generator)."""
    img = np.zeros((size, size, 3), np.float32)
    img[:] = paper
    box = cv2.boxPoints(((center[0], center[1]), wh, angle)).astype(np.int32)
    cv2.fillPoly(img, [box], spot_rgb)
    img *= brightness
    if blur > 0:
        img = cv2.GaussianBlur(img, (0, 0), blur)
    if noise > 0:
        img += np.random.default_rng(seed).normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8), box


def save_rgb(path, rgb):
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return path


@pytest.fixture
def strip_png(tmp_path):
    rgb, _ = make_strip()
    return save_rgb(tmp_path / "strip.png", rgb)
