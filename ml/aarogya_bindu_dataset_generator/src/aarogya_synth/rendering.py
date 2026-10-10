"""Rendering of the synthetic paper assay card (no augmentation of the camera here).

* ``render_clean`` - white card, one axis-aligned rectangular spot filled with
  exactly the mapped 8-bit color. No randomness: a pure function of the target.
* ``render_print`` - the same card with small, random *printing/paper*
  variation (spot color offset, gradient across the spot, darker rim, soft
  edges, low-frequency paper texture). Used as the starting canvas for
  augmented variants; camera/lighting effects are applied in augmentation.py.

All arrays are H x W x 3, RGB channel order, float in [0, 255] unless noted.
Coordinate convention: see config.py (origin top-left, x right, y down).
"""

from __future__ import annotations

import cv2
import numpy as np

from . import colorspace as cs
from .color_mapping import ColorMapping
from .config import AugmentationProfile, ImageConfig


def spot_corners(im: ImageConfig) -> np.ndarray:
    """Clean spot corners (x, y) in continuous coordinates: TL, TR, BR, BL."""
    x0, y0 = float(im.spot_x), float(im.spot_y)
    x1, y1 = x0 + im.spot_width, y0 + im.spot_height
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64)


def render_clean(im: ImageConfig, mapping: ColorMapping, target: float) -> np.ndarray:
    """Deterministic clean image (uint8). Spot pixels equal ``mapping.rgb8(target)`` exactly."""
    img = np.empty((im.height, im.width, 3), dtype=np.uint8)
    img[:] = np.asarray(im.background_rgb, dtype=np.uint8)
    img[im.spot_y : im.spot_y + im.spot_height, im.spot_x : im.spot_x + im.spot_width] = mapping.rgb8(target)
    return img


def _smooth_noise(rng: np.random.Generator, h: int, w: int, cell: int = 8) -> np.ndarray:
    """Zero-mean, unit-std low-frequency noise field (paper grain / mottling)."""
    small = rng.standard_normal((max(2, h // cell), max(2, w // cell)))
    field = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    field = cv2.GaussianBlur(field, (0, 0), sigmaX=cell / 2.0)
    std = field.std()
    return (field - field.mean()) / std if std > 0 else field * 0.0


def render_print(
    im: ImageConfig, mapping: ColorMapping, target: float, prof: AugmentationProfile, rng: np.random.Generator
) -> tuple[np.ndarray, dict]:
    """Card with printing/paper variation. Returns float RGB image and recorded parameters."""
    h, w = im.height, im.width
    base_lab = mapping.lab(target)

    # 1) Small random offset of the printed spot color (uniform direction, |dLab| <= print_delta_e_max).
    direction = rng.standard_normal(3)
    direction /= np.linalg.norm(direction) + 1e-12
    print_de = float(rng.uniform(0.0, prof.print_delta_e_max))
    spot_lab = base_lab + direction * print_de

    # 2) Linear L* gradient across the spot along a random direction.
    grad_angle = float(rng.uniform(0.0, 360.0))
    grad_dl = float(rng.uniform(0.0, prof.spot_gradient_max_delta_l))
    # 3) Darker rim near the spot edge (mimics uneven reagent deposition).
    rim = float(rng.uniform(0.0, prof.edge_darkening_max))
    rim_width = float(rng.uniform(3.0, 8.0))
    # 4) Soft edge and paper texture.
    edge_sigma = float(rng.uniform(*prof.edge_softness_sigma_px))
    texture_sigma = float(rng.uniform(*prof.paper_texture_sigma))

    sh, sw = im.spot_height, im.spot_width
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float64)
    u = ((xx + 0.5) / sw - 0.5) * np.cos(np.radians(grad_angle)) + ((yy + 0.5) / sh - 0.5) * np.sin(
        np.radians(grad_angle)
    )
    u = u / (np.abs(u).max() + 1e-12)  # in [-1, 1]
    dist_edge = np.minimum.reduce([xx + 0.5, sw - xx - 0.5, yy + 0.5, sh - yy - 0.5])
    rim_field = np.exp(-dist_edge / rim_width)

    lab_field = np.broadcast_to(spot_lab, (sh, sw, 3)).copy()
    lab_field[..., 0] += 0.5 * grad_dl * u
    lab_field[..., 0] *= 1.0 - rim * rim_field
    spot_rgb = np.clip(cs.lab_to_srgb(lab_field), 0.0, 1.0) * 255.0

    # Spot color layer: replicate the spot's border colors outward so the soft
    # (blurred) edge blends spot color with paper rather than with black.
    pad = int(np.ceil(4 * edge_sigma)) + 2
    padded = cv2.copyMakeBorder(spot_rgb, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    canvas_spot = np.zeros((h + 2 * pad, w + 2 * pad, 3), dtype=np.float64)
    canvas_spot[im.spot_y : im.spot_y + sh + 2 * pad, im.spot_x : im.spot_x + sw + 2 * pad] = padded
    canvas_spot = canvas_spot[pad : pad + h, pad : pad + w]
    mask = np.zeros((h, w), dtype=np.float64)
    mask[im.spot_y : im.spot_y + sh, im.spot_x : im.spot_x + sw] = 1.0
    if edge_sigma > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=edge_sigma)

    paper = np.empty((h, w, 3), dtype=np.float64)
    paper[:] = np.asarray(im.background_rgb, dtype=np.float64)
    img = paper * (1.0 - mask[..., None]) + canvas_spot * mask[..., None]
    img += (texture_sigma * _smooth_noise(rng, h, w))[..., None]

    params = {
        "print_delta_e": round(print_de, 4),
        "spot_gradient": {"angle_deg": round(grad_angle, 2), "delta_l": round(grad_dl, 4)},
        "edge": {"softness_sigma_px": round(edge_sigma, 4), "rim_darkening": round(rim, 4),
                 "rim_width_px": round(rim_width, 3)},
        "paper_texture_sigma": round(texture_sigma, 4),
    }
    return np.clip(img, 0.0, 255.0), params
