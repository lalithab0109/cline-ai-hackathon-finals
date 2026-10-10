"""Configurable, reproducible image-variation pipeline.

Every variant image is a pure function of (config, target, variant, seed):
``render_variant(cfg, mapping, target, variant, seed)``. All random draws come
from ``numpy.random.default_rng(seed)`` in a fixed order, and every drawn
parameter is returned so it can be recorded in the manifest.

Pipeline order (augmented variants):
    1. print/paper variation  (rendering.render_print)
    2. geometry: scale, rotation, translation, perspective (one homography)
    3. illumination field (linear or radial gradient)
    4. soft shadow (optional, heavily blurred)
    5. white balance (per-channel gains)
    6. contrast then brightness:  y = brightness * (contrast * (x - 128) + 128)
    7. blur: Gaussian (sigma) and optional disk defocus
    8. Gaussian sensor noise, then clip and round to uint8

LABEL-PRESERVATION CAVEAT: steps 3-6 intentionally change the *apparent* spot
color while the target label stays the same (an uncalibrated phone camera has
the same problem). With no reference patches on the default card, a model
cannot fully undo these shifts. The shift is recorded per image as
``apparent_delta_e_vs_clean``.
"""

from __future__ import annotations

import json

import cv2
import numpy as np

from .config import AugmentationProfile, GeneratorConfig
from .rendering import render_clean, render_print, spot_corners

MAX_GEOMETRY_DRAWS = 100


def jdump(d) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def _homography(cfg: GeneratorConfig, prof: AugmentationProfile, rng: np.random.Generator, corners: np.ndarray):
    """Draw geometry until the transformed spot stays inside the frame margin."""
    w, h = cfg.image.width, cfg.image.height
    cx, cy = w / 2.0, h / 2.0
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float64)
    margin = cfg.checks.min_margin_px
    for draw in range(MAX_GEOMETRY_DRAWS):
        rot = float(rng.uniform(-prof.rotation_max_deg, prof.rotation_max_deg))
        scale = float(rng.uniform(1.0 - prof.scale_max, 1.0 + prof.scale_max))
        tx = float(rng.uniform(-prof.translate_max_px, prof.translate_max_px))
        ty = float(rng.uniform(-prof.translate_max_px, prof.translate_max_px))
        persp = float(rng.uniform(0.0, prof.perspective_max))
        jitter = rng.uniform(-1.0, 1.0, size=(4, 2)) * persp * np.array([w, h])
        a = np.radians(rot)
        r = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]) * scale
        dst = (src - [cx, cy]) @ r.T + [cx + tx, cy + ty] + jitter
        hmat = cv2.getPerspectiveTransform(src.astype(np.float32), dst.astype(np.float32)).astype(np.float64)
        pts = cv2.perspectiveTransform(corners.reshape(-1, 1, 2), hmat).reshape(-1, 2)
        if (pts.min(axis=0) >= margin).all() and pts[:, 0].max() <= w - margin and pts[:, 1].max() <= h - margin:
            return hmat, pts, {"rotation_degrees": rot, "scale_factor": scale, "translate_x_px": tx,
                               "translate_y_px": ty, "perspective_strength": persp}
    raise RuntimeError("cannot keep the spot inside the frame; reduce geometry ranges in the profile")


def _illumination(h: int, w: int, prof: AugmentationProfile, rng: np.random.Generator):
    amp = float(rng.uniform(0.0, prof.illumination_amplitude_max))
    kind = rng.random()
    ang = float(rng.uniform(0.0, 360.0))
    px, py = float(rng.uniform(0.2, 0.8)) * w, float(rng.uniform(0.2, 0.8)) * h
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    if kind < 0.5:
        u = (xx / w - 0.5) * np.cos(np.radians(ang)) + (yy / h - 0.5) * np.sin(np.radians(ang))
        field = 1.0 + amp * u / np.abs(u).max()
        desc = {"type": "linear", "amplitude": round(amp, 4), "angle_deg": round(ang, 2)}
    else:
        d = np.hypot(xx - px, yy - py)
        field = 1.0 + amp * (1.0 - 2.0 * d / d.max())
        desc = {"type": "radial", "amplitude": round(amp, 4), "center_xy": [round(px, 1), round(py, 1)]}
    return field, desc


def _shadow(h: int, w: int, prof: AugmentationProfile, rng: np.random.Generator):
    # The same number of values is always drawn, so the random stream stays stable.
    present = rng.random() < prof.shadow_probability
    strength = float(rng.uniform(*prof.shadow_strength))
    ang = float(rng.uniform(0.0, 360.0))
    coverage = float(rng.uniform(0.15, 0.6))
    softness = float(rng.uniform(0.03, 0.10)) * max(h, w)
    if not present:
        return None, {"type": "none"}
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    nx, ny = np.cos(np.radians(ang)), np.sin(np.radians(ang))
    proj = ((xx - w / 2) * nx + (yy - h / 2) * ny) / (0.5 * np.hypot(w, h))  # ~[-1, 1]
    mask = cv2.GaussianBlur((proj > 1.0 - 2.0 * coverage).astype(np.float64), (0, 0), sigmaX=softness)
    return 1.0 - strength * mask, {"type": "soft_edge_shadow", "strength": round(strength, 4),
                                   "angle_deg": round(ang, 2), "coverage": round(coverage, 3),
                                   "softness_px": round(softness, 2)}


def _disk_kernel(radius: float) -> np.ndarray:
    r = int(np.ceil(radius))
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    k = (xx**2 + yy**2 <= radius**2).astype(np.float64)
    return k / k.sum()


def _r(x: float, n: int = 4) -> float:
    return round(float(x), n)


def render_variant(cfg: GeneratorConfig, mapping, target: float, variant: str, seed: int):
    """Render one image. Returns (uint8 RGB image, params dict for the manifest).

    ``variant == "clean"`` ignores the seed and returns the deterministic clean card.
    """
    im = cfg.image
    corners = spot_corners(im)
    if variant == "clean":
        return render_clean(im, mapping, target), {
            "brightness_factor": 1.0, "contrast_factor": 1.0, "blur_level": 0.0, "defocus_radius_px": 0.0,
            "noise_level": 0.0, "illumination_profile": jdump({"type": "none"}),
            "shadow_profile": jdump({"type": "none"}), "white_balance_profile": jdump({"r": 1.0, "g": 1.0, "b": 1.0}),
            "rotation_degrees": 0.0, "perspective_strength": 0.0, "scale_factor": 1.0,
            "translate_x_px": 0.0, "translate_y_px": 0.0, "print_profile": jdump({"type": "none"}),
            "print_delta_e": 0.0, "spot_corners_xy": corners,
        }

    prof = cfg.profiles[variant]
    rng = np.random.default_rng(seed)
    h, w = im.height, im.width
    bg = tuple(float(c) for c in im.background_rgb)

    # 1) printing / paper
    img, print_params = render_print(im, mapping, target, prof, rng)
    # 2) geometry
    hmat, pts, geo = _homography(cfg, prof, rng, corners)
    img = cv2.warpPerspective(img, hmat, (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=bg)
    # 3) illumination, 4) shadow
    illum, illum_desc = _illumination(h, w, prof, rng)
    shadow, shadow_desc = _shadow(h, w, prof, rng)
    light = illum if shadow is None else illum * shadow
    img = img * light[..., None]
    # 5) white balance
    wb = 1.0 + rng.uniform(-prof.white_balance_max, prof.white_balance_max, size=3)
    img = img * wb[None, None, :]
    # 6) contrast and brightness
    contrast = float(rng.uniform(*prof.contrast))
    brightness = float(rng.uniform(*prof.brightness))
    img = brightness * (contrast * (img - 128.0) + 128.0)
    img = np.clip(img, 0.0, 255.0)
    # 7) blur / defocus
    sigma = float(rng.uniform(*prof.blur_sigma))
    use_defocus = rng.random() < prof.defocus_probability
    defocus_r = float(rng.uniform(*prof.defocus_radius))
    if sigma > 0.05:
        img = cv2.GaussianBlur(img, (0, 0), sigmaX=sigma, borderType=cv2.BORDER_REFLECT)
    if use_defocus:
        img = cv2.filter2D(img, -1, _disk_kernel(defocus_r), borderType=cv2.BORDER_REFLECT)
    else:
        defocus_r = 0.0
    # 8) sensor noise, quantize
    noise_sigma = float(rng.uniform(*prof.noise_sigma))
    img = img + rng.normal(0.0, 1.0, size=img.shape) * noise_sigma
    out = np.clip(np.rint(img), 0, 255).astype(np.uint8)

    params = {
        "brightness_factor": _r(brightness), "contrast_factor": _r(contrast),
        "blur_level": _r(sigma), "defocus_radius_px": _r(defocus_r), "noise_level": _r(noise_sigma),
        "illumination_profile": jdump(illum_desc), "shadow_profile": jdump(shadow_desc),
        "white_balance_profile": jdump({"r": _r(wb[0]), "g": _r(wb[1]), "b": _r(wb[2])}),
        "rotation_degrees": _r(geo["rotation_degrees"]), "perspective_strength": _r(geo["perspective_strength"], 5),
        "scale_factor": _r(geo["scale_factor"]), "translate_x_px": _r(geo["translate_x_px"], 2),
        "translate_y_px": _r(geo["translate_y_px"], 2), "print_profile": jdump(print_params),
        "print_delta_e": print_params["print_delta_e"], "spot_corners_xy": pts,
    }
    return out, params
