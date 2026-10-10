"""Reference reaction-spot localisation and color-feature extraction.

Used by the validator and provided as a *reference implementation* for the
backend. It needs no labels or manifest metadata: input is just an image.

ROI detection (``detect_spot``):
    1. light Gaussian blur
    2. per-pixel saturation S = (max - min) / max  (paper ~ low S, spot ~ high S)
    3. Otsu threshold on S (floored at ``min_saturation``) + morphological clean-up
    4. largest external contour -> ``cv2.minAreaRect`` -> 4 corner points
    5. analysis ROI = that rectangle shrunk toward its center by ``shrink``
       (default 15 %) to avoid soft edges and rim effects

Features (``extract_features``), computed over ROI pixels:
    rgb_median_{r,g,b}, rgb_mean_{r,g,b}, rgb_std_{r,g,b}           8-bit scale
    hsv_h_circmean_deg, hsv_h_circstd_deg                              0..360 deg
    hsv_{s,v}_{mean,std}                                               0..1
    lab_{l,a,b}_{mean,median,std}                                      true CIELAB (D65)
    lab_l_iqr, roi_pixel_count, roi_area_fraction
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from . import colorspace as cs


class SpotNotFoundError(RuntimeError):
    pass


def load_rgb(path: str | Path) -> np.ndarray:
    """Read PNG/JPEG as uint8 RGB (H, W, 3). Raises on unreadable files."""
    data = np.fromfile(str(path), dtype=np.uint8)  # works with non-ASCII Windows paths
    bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if bgr is None:
        raise OSError(f"unreadable image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def shrink_polygon(pts: np.ndarray, shrink: float) -> np.ndarray:
    c = pts.mean(axis=0)
    return c + (pts - c) * (1.0 - shrink)


def polygon_mask(shape_hw: tuple[int, int], pts: np.ndarray) -> np.ndarray:
    """Boolean mask of a polygon given in continuous (x, y) coordinates."""
    mask = np.zeros(shape_hw, dtype=np.uint8)
    # pixel centers are at integer + 0.5 -> shift by -0.5 for OpenCV's integer grid
    p = np.round((np.asarray(pts, dtype=np.float64) - 0.5) * 16).astype(np.int32)
    cv2.fillPoly(mask, [p], 1, lineType=cv2.LINE_8, shift=4)
    return mask.astype(bool)


def _saturation8(rgb: np.ndarray) -> np.ndarray:
    img = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), 1.5)
    mx, mn = img.max(axis=2), img.min(axis=2)
    sat = np.where(mx > 1e-3, (mx - mn) / np.maximum(mx, 1e-3), 0.0)
    return np.clip(sat * 255.0, 0, 255).astype(np.uint8)


def detect_spot(rgb: np.ndarray, min_saturation: float = 0.10, min_area_fraction: float = 0.005,
                min_fill: float = 0.80) -> np.ndarray:
    """Return the 4 corners (x, y) of the detected rectangular spot.

    A threshold sweep on saturation (Otsu plus fixed levels) yields candidate
    regions. Candidates touching the image border (e.g. tinted shadows) or that
    are not rectangle-like (contour area / min-area-rectangle area < min_fill)
    are rejected; among the rest the one with the largest area * fill wins.
    """
    sat8 = _saturation8(rgb)
    h, w = sat8.shape
    otsu, _ = cv2.threshold(sat8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    levels = sorted({int(otsu)} | {int(v * 255) for v in (0.10, 0.15, 0.20, 0.28, 0.36, 0.45)})
    levels = [t for t in levels if t >= min_saturation * 255]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    best, best_score = None, -1.0
    for thr in levels:
        binary = (sat8 > thr).astype(np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area_fraction * h * w:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
                continue  # touches the border: not the printed spot
            rect = cv2.minAreaRect(cnt)
            fill = area / max(rect[1][0] * rect[1][1], 1e-6)
            if fill < min_fill:
                continue
            score = area * fill
            if score > best_score:
                best, best_score = rect, score
    if best is None:
        raise SpotNotFoundError("no rectangular colored region found")
    return cv2.boxPoints(best).astype(np.float64) + 0.5  # pixel indices -> continuous coordinates


def polygon_iou(a: np.ndarray, b: np.ndarray, shape_hw: tuple[int, int]) -> float:
    ma, mb = polygon_mask(shape_hw, a), polygon_mask(shape_hw, b)
    union = np.logical_or(ma, mb).sum()
    return float(np.logical_and(ma, mb).sum() / union) if union else 0.0


def roi_pixels(rgb: np.ndarray, corners: np.ndarray, shrink: float = 0.15) -> np.ndarray:
    mask = polygon_mask(rgb.shape[:2], shrink_polygon(np.asarray(corners, float), shrink))
    px = rgb[mask]
    if len(px) == 0:
        raise SpotNotFoundError("empty ROI")
    return px


def paper_pixels(rgb: np.ndarray, corners: np.ndarray, grow: float = 0.35) -> np.ndarray:
    """Pixels in a ring outside the spot (for spot-vs-paper contrast checks)."""
    hw = rgb.shape[:2]
    c = np.asarray(corners, float)
    outer = polygon_mask(hw, shrink_polygon(c, -grow))
    inner = polygon_mask(hw, shrink_polygon(c, -0.08))
    return rgb[outer & ~inner]


def color_features(px: np.ndarray) -> dict[str, float]:
    """Color statistics of an (N, 3) uint8 RGB pixel array."""
    px = np.asarray(px)
    f = px.astype(np.float64)
    feats: dict[str, float] = {}
    for i, ch in enumerate("rgb"):
        feats[f"rgb_median_{ch}"] = float(np.median(f[:, i]))
        feats[f"rgb_mean_{ch}"] = float(f[:, i].mean())
        feats[f"rgb_std_{ch}"] = float(f[:, i].std())
    # HSV on [0, 1] floats: hue in degrees 0..360 (NOT OpenCV's 0..179 uint8 scale)
    hsv = cv2.cvtColor((f / 255.0).astype(np.float32).reshape(-1, 1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3)
    hue = np.radians(hsv[:, 0].astype(np.float64))
    c, s = np.cos(hue).mean(), np.sin(hue).mean()
    feats["hsv_h_circmean_deg"] = float(np.degrees(np.arctan2(s, c)) % 360.0)
    resultant = min(max(float(np.hypot(c, s)), 1e-12), 1.0)  # clamp float round-off (uniform hue -> 1.0)
    feats["hsv_h_circstd_deg"] = float(np.degrees(np.sqrt(max(-2.0 * np.log(resultant), 0.0))))
    for i, ch in ((1, "s"), (2, "v")):
        feats[f"hsv_{ch}_mean"] = float(hsv[:, i].mean())
        feats[f"hsv_{ch}_std"] = float(hsv[:, i].std())
    lab = cs.srgb8_to_lab(f)
    for i, ch in enumerate("lab"):
        feats[f"lab_{ch}_mean"] = float(lab[:, i].mean())
        feats[f"lab_{ch}_median"] = float(np.median(lab[:, i]))
        feats[f"lab_{ch}_std"] = float(lab[:, i].std())
    q75, q25 = np.percentile(lab[:, 0], [75, 25])
    feats["lab_l_iqr"] = float(q75 - q25)
    feats["roi_pixel_count"] = float(len(px))
    return feats


def extract_features(rgb: np.ndarray, corners: np.ndarray | None = None, shrink: float = 0.15) -> dict[str, float]:
    """Detect the spot (unless ``corners`` is given) and return color features.

    At inference time pass ``corners=None``; ``spot_corners_xy`` from the
    manifest is ground-truth geometry intended only for debugging/evaluation.
    """
    if corners is None:
        corners = detect_spot(rgb)
    px = roi_pixels(rgb, corners, shrink)
    feats = color_features(px)
    feats["roi_area_fraction"] = float(len(px) / (rgb.shape[0] * rgb.shape[1]))
    return feats
