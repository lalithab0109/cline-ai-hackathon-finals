"""Hand-crafted color features from a preprocessed spot.

Two named feature sets are compared during training:

* ``raw_color``   - color statistics of the interior ROI only (no background use).
* ``normalized``  - ROI color divided by the paper-white estimate
                    (white-background normalization, NOT calibration), plus
                    absorbance-like and contrast-to-background features.

Hue is encoded circularly (sin/cos) so 359 deg and 1 deg are close. Quality
metrics are exported alongside but are NOT model inputs (they describe the
capture, not the analyte).
"""

from __future__ import annotations

import cv2
import numpy as np

from .preprocessing import Preprocessed

EPS = 1e-6


def _lab(rgb01: np.ndarray) -> np.ndarray:
    """sRGB (0..1, shape (...,3)) -> CIE Lab (D65) via OpenCV float path (L 0..100)."""
    arr = np.clip(np.asarray(rgb01, np.float32).reshape(-1, 1, 3), 0, 1)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2Lab).reshape(np.shape(rgb01))


def _hsv_circ(rgb01: np.ndarray) -> tuple[float, float, float, float]:
    arr = np.clip(np.asarray(rgb01, np.float32).reshape(1, 1, 3), 0, 1)
    h, s, v = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV).reshape(3)  # h in degrees for float input
    rad = np.deg2rad(float(h))
    return float(np.sin(rad)), float(np.cos(rad)), float(s), float(v)


def _color_block(prefix: str, rgb01: np.ndarray) -> dict:
    r, g, b = (float(x) for x in rgb01)
    L, a, bb = (float(x) for x in _lab(rgb01))
    hs, hc, s, v = _hsv_circ(rgb01)
    tot = r + g + b + EPS
    return {
        f"{prefix}_r": r, f"{prefix}_g": g, f"{prefix}_b": b,
        f"{prefix}_L": L, f"{prefix}_a": a, f"{prefix}_bstar": bb,
        f"{prefix}_chroma": float(np.hypot(a, bb)),
        f"{prefix}_hab_sin": float(np.sin(np.arctan2(bb, a))), f"{prefix}_hab_cos": float(np.cos(np.arctan2(bb, a))),
        f"{prefix}_hue_sin": hs, f"{prefix}_hue_cos": hc, f"{prefix}_sat": s, f"{prefix}_val": v,
        f"{prefix}_chrom_r": r / tot, f"{prefix}_chrom_g": g / tot,
        f"{prefix}_g_over_r": g / (r + EPS), f"{prefix}_b_over_r": b / (r + EPS), f"{prefix}_b_over_g": b / (g + EPS),
    }


RAW_FEATURES = [f"raw_{k}" for k in ("r", "g", "b", "L", "a", "bstar", "chroma", "hab_sin", "hab_cos", "hue_sin",
                                      "hue_cos", "sat", "val", "chrom_r", "chrom_g", "g_over_r", "b_over_r",
                                      "b_over_g")] + ["raw_r_std", "raw_g_std", "raw_b_std"]
NORM_FEATURES = [f"norm_{k}" for k in ("r", "g", "b", "L", "a", "bstar", "chroma", "hab_sin", "hab_cos", "hue_sin",
                                        "hue_cos", "sat", "val", "chrom_r", "chrom_g", "g_over_r", "b_over_r",
                                        "b_over_g")] + [
    "absorb_r", "absorb_g", "absorb_b", "absorb_g_minus_b", "absorb_g_over_sum",
    "contrast_deltaE", "contrast_dL", "contrast_dchroma", "raw_chrom_r", "raw_chrom_g", "raw_hab_sin", "raw_hab_cos"]
FEATURE_SETS = {"raw_color": RAW_FEATURES, "normalized": NORM_FEATURES}
QUALITY_COLUMNS = ["q_sharpness", "q_clipped_fraction", "q_paper_brightness", "q_roi_color_std",
                   "q_detection_confidence", "q_paper_r", "q_paper_g", "q_paper_b"]


def extract_features(pre: Preprocessed) -> dict:
    """Return a flat dict with every feature in all sets plus quality columns. Requires ``pre.ok``."""
    if pre.roi_pixels is None or pre.paper_white is None:
        raise ValueError("cannot extract features: preprocessing produced no ROI / background estimate")
    roi = pre.roi_pixels.astype(np.float64) / 255.0
    med = np.median(roi, axis=0)
    std = roi.std(axis=0)
    white = np.clip(pre.paper_white / 255.0, 1e-3, 1.0)
    norm = np.clip(med / white, 1e-3, 1.5)
    feats = {}
    feats.update(_color_block("raw", med))
    feats.update({"raw_r_std": float(std[0]), "raw_g_std": float(std[1]), "raw_b_std": float(std[2])})
    feats.update(_color_block("norm", np.clip(norm, 0, 1)))
    absorb = -np.log10(norm)
    feats.update({"absorb_r": float(absorb[0]), "absorb_g": float(absorb[1]), "absorb_b": float(absorb[2]),
                  "absorb_g_minus_b": float(absorb[1] - absorb[2]),
                  "absorb_g_over_sum": float(absorb[1] / (absorb.sum() + EPS))})
    lab_spot, lab_paper = _lab(med), _lab(white)
    feats.update({"contrast_deltaE": float(np.linalg.norm(lab_spot - lab_paper)),
                  "contrast_dL": float(lab_paper[0] - lab_spot[0]),
                  "contrast_dchroma": float(np.hypot(*lab_spot[1:]) - np.hypot(*lab_paper[1:]))})
    q = pre.quality
    feats.update({"q_sharpness": q.get("sharpness_laplacian_var"), "q_clipped_fraction": q.get("roi_clipped_fraction"),
                  "q_paper_brightness": q.get("paper_brightness"), "q_roi_color_std": q.get("roi_color_std"),
                  "q_detection_confidence": q.get("detection_confidence"),
                  "q_paper_r": float(pre.paper_white[0]), "q_paper_g": float(pre.paper_white[1]),
                  "q_paper_b": float(pre.paper_white[2])})
    for k, val in feats.items():
        if val is None or not np.isfinite(val):
            raise ValueError(f"non-finite feature {k}={val}")
    return feats


def feature_vector(feats: dict, names: list[str]) -> np.ndarray:
    """Order features exactly as the model expects; missing names raise KeyError."""
    return np.array([[feats[n] for n in names]], dtype=np.float64)
