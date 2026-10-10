"""OpenCV preprocessing: load -> validate -> detect reaction rectangle -> rectify -> ROI -> quality.

Detection uses only image content (no fixed coordinates, no manifest corners):

1. Light Gaussian blur (noise robustness).
2. "Colorfulness" map S = (max - min) / max per pixel. White/grey paper has low
   S regardless of brightness, so S is robust to brightness changes and
   uneven illumination; a tinted shadow has much lower S than the dye spot.
3. Several thresholds (Otsu + fixed levels) -> morphology -> external contours.
4. Candidates are rejected if too small / too large, touching the border,
   not rectangle-like (contour fill vs. min-area rectangle), or with implausible
   aspect ratio. Remaining candidates are scored by area x fill x mean S.
5. The best contour is approximated by a quadrilateral (``approxPolyDP``) when
   possible (handles perspective), otherwise ``minAreaRect``.
6. Perspective rectification to a fixed canonical patch (rotation/perspective
   correction), then an interior ROI that excludes a border margin.

Color normalization (NOT calibration): the images contain no reference patches
with known colors, so true colorimetric calibration is impossible. We instead
estimate the paper white from a ring of background pixels around the spot and
divide each channel by it ("white-background normalization", a von-Kries-style
correction). This compensates global brightness/white-balance shifts only to
the extent that the paper is truly white and lit like the spot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from . import config as C

CANON_W, CANON_H = 160, 120  # rectified patch size (landscape)
ROI_MARGIN = 0.18  # fraction of each side excluded from the interior ROI
MIN_AREA_FRAC, MAX_AREA_FRAC = 0.01, 0.50
MIN_FILL = 0.80
MAX_ASPECT = 4.0
BLUR_MIN_LAPLACIAN = 2.0  # images below this sharpness are flagged (see quality)
MAX_CLIPPED_FRAC = 0.05


class ImageLoadError(ValueError):
    """Unreadable, corrupt, non-image or wrongly shaped input."""


@dataclass
class Detection:
    ok: bool
    corners: np.ndarray | None = None  # 4x2 (x, y), ordered TL, TR, BR, BL
    confidence: float = 0.0
    method: str = ""
    failure_reason: str = ""
    candidates: int = 0
    metrics: dict = field(default_factory=dict)


def load_image_rgb(path_or_bytes, expected_size: tuple[int, int] | None = None) -> np.ndarray:
    """Read PNG/JPEG into uint8 RGB (H, W, 3). Raises ImageLoadError on any problem."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        buf = np.frombuffer(path_or_bytes, dtype=np.uint8)
        name = "<bytes>"
    else:
        p = Path(path_or_bytes)
        if not p.is_file():
            raise ImageLoadError(f"file not found: {p}")
        buf = np.fromfile(str(p), dtype=np.uint8)
        name = str(p)
    if buf.size == 0:
        raise ImageLoadError(f"empty file: {name}")
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ImageLoadError(f"not a decodable image (corrupt or unsupported format): {name}")
    if img.dtype != np.uint8:
        raise ImageLoadError(f"unsupported bit depth {img.dtype}; expected 8-bit")
    if img.ndim == 2:
        raise ImageLoadError("grayscale image; expected 3-channel RGB")
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    elif img.shape[2] != 3:
        raise ImageLoadError(f"unsupported channel count {img.shape[2]}")
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if expected_size is not None and (rgb.shape[1], rgb.shape[0]) != tuple(expected_size):
        raise ImageLoadError(f"image size {rgb.shape[1]}x{rgb.shape[0]} != expected {expected_size[0]}x{expected_size[1]}")
    if min(rgb.shape[:2]) < 64:
        raise ImageLoadError("image too small (< 64 px)")
    return rgb


def colorfulness_map(rgb: np.ndarray) -> np.ndarray:
    img = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), 1.5)
    mx, mn = img.max(axis=2), img.min(axis=2)
    return np.where(mx > 1.0, (mx - mn) / np.maximum(mx, 1.0), 0.0).astype(np.float32)


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Order 4 points TL, TR, BR, BL and make the first edge the long one (landscape)."""
    pts = np.asarray(pts, dtype=np.float64).reshape(4, 2)
    c = pts.mean(axis=0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    pts = pts[np.argsort(ang)]  # clockwise in image coords starting near -pi (left)
    start = int(np.argmin(pts.sum(axis=1)))  # top-left = min(x+y)
    pts = np.roll(pts, -start, axis=0)
    if np.linalg.norm(pts[1] - pts[0]) < np.linalg.norm(pts[3] - pts[0]):
        pts = np.roll(pts, -1, axis=0)  # portrait -> rotate labels so width is the long edge
    return pts


def detect_reaction_region(rgb: np.ndarray) -> Detection:
    """Find the most plausible colored rectangle. Never uses fixed coordinates."""
    h, w = rgb.shape[:2]
    sat = colorfulness_map(rgb)
    sat8 = np.clip(sat * 255, 0, 255).astype(np.uint8)
    otsu, _ = cv2.threshold(sat8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    levels = sorted({int(otsu)} | {int(x * 255) for x in (0.10, 0.15, 0.20, 0.28, 0.36, 0.45)})
    levels = [t for t in levels if t >= int(0.08 * 255)]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    best, n_cand, reasons = None, 0, set()
    for thr in levels:
        binary = (sat8 > thr).astype(np.uint8)
        binary = cv2.morphologyEx(cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel), cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < MIN_AREA_FRAC * h * w:
                reasons.add("too_small")
                continue
            if area > MAX_AREA_FRAC * h * w:
                reasons.add("too_large")
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
                reasons.add("touches_border")
                continue
            rect = cv2.minAreaRect(cnt)
            rw, rh = rect[1]
            fill = area / max(rw * rh, 1e-6)
            aspect = max(rw, rh) / max(min(rw, rh), 1e-6)
            if fill < MIN_FILL:
                reasons.add("not_rectangular")
                continue
            if aspect > MAX_ASPECT:
                reasons.add("implausible_aspect")
                continue
            n_cand += 1
            m = np.zeros((h, w), np.uint8)
            cv2.drawContours(m, [cnt], -1, 1, -1)
            mean_sat = float(sat[m.astype(bool)].mean())
            score = area * fill * mean_sat
            if best is None or score > best[0]:
                best = (score, cnt, rect, fill, aspect, mean_sat, thr)
    if best is None:
        why = ",".join(sorted(reasons)) or "no_colored_region"
        return Detection(False, failure_reason=f"no plausible reaction rectangle ({why})", candidates=0)
    _, cnt, rect, fill, aspect, mean_sat, thr = best
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    if len(approx) == 4 and cv2.isContourConvex(approx):
        corners, method = approx.reshape(4, 2).astype(np.float64) + 0.5, "quad_approx"
    else:
        corners, method = cv2.boxPoints(rect).astype(np.float64) + 0.5, "min_area_rect"
    corners = order_corners(corners)
    paper = sat[_ring_mask((h, w), corners)]
    paper_sat = float(np.median(paper)) if paper.size else 0.0
    separation = float(np.clip((mean_sat - paper_sat) / 0.25, 0, 1))
    confidence = float(np.clip(((fill - MIN_FILL) / (1 - MIN_FILL)) * 0.5 + separation * 0.5, 0, 1))
    return Detection(True, corners, round(confidence, 4), method, "", n_cand,
                     {"fill": round(float(fill), 4), "aspect": round(float(aspect), 3),
                      "spot_colorfulness": round(mean_sat, 4), "paper_colorfulness": round(paper_sat, 4),
                      "threshold": int(thr), "area_px": float(cv2.contourArea(cnt))})


def _poly_mask(shape_hw, pts) -> np.ndarray:
    m = np.zeros(shape_hw, np.uint8)
    p = np.round((np.asarray(pts, float) - 0.5) * 16).astype(np.int32)
    cv2.fillPoly(m, [p], 1, lineType=cv2.LINE_8, shift=4)
    return m.astype(bool)


def _scale_poly(pts, factor) -> np.ndarray:
    c = pts.mean(axis=0)
    return c + (pts - c) * factor


def _ring_mask(shape_hw, corners, inner=1.12, outer=1.45) -> np.ndarray:
    """Background ring around the spot (excludes the spot and its soft edge)."""
    return _poly_mask(shape_hw, _scale_poly(corners, outer)) & ~_poly_mask(shape_hw, _scale_poly(corners, inner))


def rectify(rgb: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Perspective-correct the spot into a CANON_W x CANON_H patch (rotation/perspective removed)."""
    dst = np.array([[0, 0], [CANON_W, 0], [CANON_W, CANON_H], [0, CANON_H]], np.float32)
    H = cv2.getPerspectiveTransform((corners - 0.5).astype(np.float32), dst)
    return cv2.warpPerspective(rgb, H, (CANON_W, CANON_H), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REPLICATE)


def interior_roi(patch: np.ndarray, margin: float = ROI_MARGIN) -> tuple[np.ndarray, np.ndarray]:
    """Return (ROI pixels Nx3, boolean mask over the patch) excluding a border margin."""
    ph, pw = patch.shape[:2]
    mask = np.zeros((ph, pw), bool)
    mx, my = int(round(pw * margin)), int(round(ph * margin))
    mask[my:ph - my, mx:pw - mx] = True
    return patch[mask], mask


@dataclass
class Preprocessed:
    """Everything downstream steps need. ``ok`` False means no measurement may be produced."""

    ok: bool
    status: str  # "ok" | "load_failed" | "detection_failed" | "quality_failed"
    issues: list[str]
    rgb: np.ndarray | None = None
    detection: Detection | None = None
    patch: np.ndarray | None = None  # rectified spot, uint8 RGB
    roi_pixels: np.ndarray | None = None  # Nx3 uint8 RGB (raw)
    paper_pixels: np.ndarray | None = None  # Mx3 uint8 RGB (background ring)
    paper_white: np.ndarray | None = None  # robust paper color estimate (float RGB)
    quality: dict = field(default_factory=dict)


def assess_quality(rgb: np.ndarray, det: Detection, roi: np.ndarray, paper: np.ndarray) -> tuple[list[str], dict]:
    """Quality metrics + blocking issues. Thresholds are documented constants (not learned)."""
    issues = []
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    x0, y0 = np.floor(det.corners.min(axis=0)).astype(int)
    x1, y1 = np.ceil(det.corners.max(axis=0)).astype(int)
    pad = 12
    crop = gray[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
    sharp = float(cv2.Laplacian(crop, cv2.CV_64F).var())
    # Light (low-target) colors legitimately have R near 255, so a single saturated channel is
    # recorded but not blocking; >=2 saturated channels means the hue itself is unrecoverable.
    ch_clip = (roi >= 254) | (roi <= 1)
    clipped = float(np.mean(ch_clip.sum(axis=1) >= 2))
    single = float(np.mean(ch_clip.any(axis=1)))
    paper_med = np.median(paper, axis=0) if len(paper) else np.array([np.nan] * 3)
    paper_lum = float(np.mean(paper_med))
    roi_std = float(roi.astype(float).std(axis=0).mean())
    metrics = {
        "sharpness_laplacian_var": round(sharp, 3),
        "roi_clipped_fraction": round(clipped, 4),
        "roi_single_channel_clipped_fraction": round(single, 4),
        "paper_brightness": round(paper_lum, 2),
        "roi_color_std": round(roi_std, 3),
        "roi_pixel_count": int(len(roi)),
        "detection_confidence": det.confidence,
    }
    if det.confidence < 0.35:
        issues.append(f"low_detection_confidence ({det.confidence:.2f} < 0.35)")
    if clipped > MAX_CLIPPED_FRAC:
        issues.append(f"overexposed_or_clipped_roi ({clipped:.1%} pixels with >=2 saturated channels > {MAX_CLIPPED_FRAC:.0%})")
    if not np.isfinite(paper_lum) or paper_lum < 90:
        issues.append(f"background_too_dark_for_white_normalization (paper brightness {paper_lum:.0f} < 90)")
    if sharp < BLUR_MIN_LAPLACIAN:
        issues.append(f"too_blurry (laplacian variance {sharp:.2f} < {BLUR_MIN_LAPLACIAN})")
    if len(roi) < 500:
        issues.append(f"roi_too_small ({len(roi)} px < 500)")
    if roi_std > 25:
        issues.append(f"roi_not_uniform (mean channel std {roi_std:.1f} > 25)")
    return issues, metrics


def preprocess(image, expected_size: tuple[int, int] | None = C.EXPECTED_SIZE) -> Preprocessed:
    """Full preprocessing. ``image`` may be a path, raw bytes, or an RGB uint8 array."""
    try:
        if isinstance(image, np.ndarray):
            if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
                raise ImageLoadError("array input must be uint8 RGB (H, W, 3)")
            if expected_size and (image.shape[1], image.shape[0]) != tuple(expected_size):
                raise ImageLoadError(f"image size {image.shape[1]}x{image.shape[0]} != expected {expected_size}")
            rgb = image
        else:
            rgb = load_image_rgb(image, expected_size)
    except ImageLoadError as exc:
        return Preprocessed(False, "load_failed", [f"invalid_image: {exc}"])
    det = detect_reaction_region(rgb)
    if not det.ok:
        return Preprocessed(False, "detection_failed", [det.failure_reason], rgb=rgb, detection=det)
    patch = rectify(rgb, det.corners)
    roi, _ = interior_roi(patch)
    paper = rgb[_ring_mask(rgb.shape[:2], det.corners)]
    # robust paper-white estimate: brightest 50 % of ring pixels (avoids shadow / edge bleed)
    if len(paper):
        lum = paper.astype(float).mean(axis=1)
        paper_white = np.median(paper[lum >= np.median(lum)].astype(float), axis=0)
    else:
        paper_white = None
    issues, qm = assess_quality(rgb, det, roi, paper)
    status = "ok" if not issues else "quality_failed"
    return Preprocessed(not issues, status, issues, rgb, det, patch, roi, paper, paper_white, qm)


def annotate(pre: Preprocessed, title: str = "") -> np.ndarray:
    """RGB visualization: detected rectangle (green/red), interior ROI (yellow), paper ring, status text."""
    if pre.rgb is None:
        canvas = np.full((256, 256, 3), 230, np.uint8)
        cv2.putText(canvas, "LOAD FAILED", (20, 128), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 0, 0), 2)
        return canvas
    vis = pre.rgb.copy()
    if pre.detection is not None and pre.detection.ok:
        c = pre.detection.corners
        ring = _ring_mask(vis.shape[:2], c)
        vis[ring] = (0.7 * vis[ring] + 0.3 * np.array([80, 160, 255])).astype(np.uint8)
        color = (0, 170, 0) if pre.ok else (220, 0, 0)
        cv2.polylines(vis, [np.round(c - 0.5).astype(np.int32)], True, color, 2, cv2.LINE_AA)
        inner = _scale_poly(c, 1 - 2 * ROI_MARGIN)
        cv2.polylines(vis, [np.round(inner - 0.5).astype(np.int32)], True, (255, 210, 0), 2, cv2.LINE_AA)
        txt = f"conf {pre.detection.confidence:.2f} | {pre.detection.method}"
    else:
        txt = "NO ROI"
    cv2.putText(vis, txt, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(vis, txt, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    status = pre.status.upper() + ("" if pre.ok else ": " + "; ".join(i.split(" (")[0] for i in pre.issues))
    for k, line in enumerate([status[i:i + 48] for i in range(0, len(status), 48)][:3]):
        y = vis.shape[0] - 12 - 20 * (2 - k)
        cv2.putText(vis, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(vis, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255) if pre.ok else (255, 120, 120), 1, cv2.LINE_AA)
    if title:
        cv2.putText(vis, title, (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return vis
