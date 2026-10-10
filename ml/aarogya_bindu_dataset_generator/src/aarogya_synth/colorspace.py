"""Color-space conversions (sRGB <-> linear RGB <-> CIE XYZ <-> CIELAB), D65 white.

Implemented in NumPy so results are deterministic and independent of OpenCV's
8-bit Lab scaling. All functions accept arrays whose last axis has length 3.

* sRGB values are floats in [0, 1] (divide 8-bit values by 255).
* CIELAB values are true L* in [0, 100], a*, b* unscaled.
"""

from __future__ import annotations

import numpy as np

# sRGB (IEC 61966-2-1) primaries, D65 reference white.
M_RGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
M_XYZ_TO_RGB = np.linalg.inv(M_RGB_TO_XYZ)
D65_WHITE = M_RGB_TO_XYZ.sum(axis=1)  # (0.95047, 1.0, 1.08883)

_DELTA = 6.0 / 29.0


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((np.maximum(c, 0.0) + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.maximum(c, 0.0), 1.0 / 2.4) - 0.055)


def xyz_to_lab(xyz):
    t = np.asarray(xyz, dtype=np.float64) / D65_WHITE
    f = np.where(t > _DELTA**3, np.cbrt(t), t / (3 * _DELTA**2) + 4.0 / 29.0)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return np.stack([116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)], axis=-1)


def lab_to_xyz(lab):
    lab = np.asarray(lab, dtype=np.float64)
    fy = (lab[..., 0] + 16.0) / 116.0
    fx = fy + lab[..., 1] / 500.0
    fz = fy - lab[..., 2] / 200.0
    f = np.stack([fx, fy, fz], axis=-1)
    t = np.where(f > _DELTA, f**3, 3 * _DELTA**2 * (f - 4.0 / 29.0))
    return t * D65_WHITE


def lab_to_linear_rgb(lab):
    return lab_to_xyz(lab) @ M_XYZ_TO_RGB.T


def lab_to_srgb(lab):
    """CIELAB -> sRGB float (NOT clipped; caller decides how to handle out-of-gamut)."""
    return linear_to_srgb(lab_to_linear_rgb(lab))


def srgb_to_lab(rgb01):
    return xyz_to_lab(srgb_to_linear(rgb01) @ M_RGB_TO_XYZ.T)


def srgb8_to_lab(rgb8):
    return srgb_to_lab(np.asarray(rgb8, dtype=np.float64) / 255.0)


def in_srgb_gamut(lab, tol: float = 1e-9):
    """Boolean array: True where the Lab color is representable in sRGB."""
    lin = lab_to_linear_rgb(lab)
    return np.all((lin >= -tol) & (lin <= 1.0 + tol), axis=-1)


def delta_e76(lab1, lab2):
    """CIE76 color difference (Euclidean distance in CIELAB)."""
    return np.linalg.norm(np.asarray(lab1, float) - np.asarray(lab2, float), axis=-1)
