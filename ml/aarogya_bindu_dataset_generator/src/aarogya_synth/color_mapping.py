"""Target -> color mapping (kept separate from image rendering).

SYNTHETIC DESIGN CHOICE - NOT A CLINICAL OR EXPERIMENTAL CALIBRATION CURVE.

Synthetic mapping ``synthetic_lab_linear`` (default)
----------------------------------------------------
For a simulated target c (g/dL) and parameters (c_min, c_max, gamma, Lab_low, Lab_high):

    t      = clip((c - c_min) / (c_max - c_min), 0, 1)
    s      = t ** gamma                      (gamma > 0  ->  strictly increasing)
    Lab(c) = Lab_low + s * (Lab_high - Lab_low)
    RGB(c) = sRGB_D65(Lab(c))                (CIELAB -> XYZ -> linear RGB -> sRGB)
    RGB8   = round(255 * RGB(c))

Interpolating in CIELAB (approximately perceptually uniform) gives smooth,
evenly spaced color steps. L* is linear in s and L*_low != L*_high, so L* is
strictly monotonic in c (darker spot = higher simulated target with defaults).
The whole curve is checked to lie inside the sRGB gamut when the mapping is
built; an out-of-gamut configuration raises an error instead of being clipped.

Replacing with real data later: ``CalibrationTableMapping`` takes (target, L*,
a*, b*) points - e.g. median spot colors of real assay photographs paired with
independently measured reference values - and interpolates piecewise linearly.
Both classes share the same interface, so the renderer does not change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from . import colorspace as cs
from .config import ConfigError, MappingConfig

GAMUT_CHECK_POINTS = 1001


class ColorMapping:
    """Interface: map a simulated target value (scalar or array) to a color."""

    mapping_id: str
    target_min: float
    target_max: float

    def lab(self, target) -> np.ndarray:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        raise NotImplementedError

    def rgb01(self, target) -> np.ndarray:
        """sRGB in [0, 1]. Gamut is pre-checked, so clipping only removes float round-off."""
        return np.clip(cs.lab_to_srgb(self.lab(target)), 0.0, 1.0)

    def rgb8(self, target) -> np.ndarray:
        return np.round(self.rgb01(target) * 255.0).astype(np.uint8)

    def _check(self) -> None:
        grid = np.linspace(self.target_min, self.target_max, GAMUT_CHECK_POINTS)
        lab = self.lab(grid)
        ok = cs.in_srgb_gamut(lab, tol=1e-6)
        if not np.all(ok):
            bad = grid[~ok]
            raise ConfigError(
                f"color mapping leaves the sRGB gamut for targets {bad.min():.3f}..{bad.max():.3f}; "
                "adjust the Lab anchors"
            )
        dl = np.diff(lab[:, 0])
        if not (np.all(dl < 0) or np.all(dl > 0)):
            raise ConfigError("color mapping L* is not strictly monotonic over the target range")

    def l_direction(self) -> int:
        """-1 if L* decreases with target (default), +1 if it increases."""
        l0, l1 = self.lab(np.array([self.target_min, self.target_max]))[:, 0]
        return 1 if l1 > l0 else -1

    def table(self, n: int = 57) -> list[dict[str, float]]:
        grid = np.linspace(self.target_min, self.target_max, n)
        lab, rgb = self.lab(grid), self.rgb8(grid)
        return [
            {"target_hb_g_dl": round(float(g), 4), "L": round(float(l[0]), 4), "a": round(float(l[1]), 4),
             "b": round(float(l[2]), 4), "R": int(c[0]), "G": int(c[1]), "B": int(c[2])}
            for g, l, c in zip(grid, lab, rgb)
        ]


class SyntheticLabLinearMapping(ColorMapping):
    """Smooth, monotonic synthetic mapping. Equation in the module docstring."""

    def __init__(self, target_min, target_max, gamma, lab_low, lab_high, mapping_id="synthetic_lab_linear_v1"):
        self.mapping_id = mapping_id
        self.target_min = float(target_min)
        self.target_max = float(target_max)
        self.gamma = float(gamma)
        self.lab_low = np.asarray(lab_low, dtype=np.float64)
        self.lab_high = np.asarray(lab_high, dtype=np.float64)
        if self.target_max <= self.target_min or self.gamma <= 0:
            raise ConfigError("invalid synthetic mapping parameters")
        if self.lab_low.shape != (3,) or self.lab_high.shape != (3,):
            raise ConfigError("lab_low and lab_high must be [L, a, b]")
        if self.lab_low[0] == self.lab_high[0]:
            raise ConfigError("lab_low and lab_high must have different L* (monotonicity)")
        self._check()

    def lab(self, target) -> np.ndarray:
        c = np.asarray(target, dtype=np.float64)
        t = np.clip((c - self.target_min) / (self.target_max - self.target_min), 0.0, 1.0)
        s = t**self.gamma
        return self.lab_low + s[..., None] * (self.lab_high - self.lab_low)

    def describe(self) -> dict[str, Any]:
        return {
            "type": "synthetic_lab_linear",
            "mapping_id": self.mapping_id,
            "nature": "SYNTHETIC design choice; not a clinical or experimental calibration curve",
            "color_space": "CIELAB (D65 white), converted to 8-bit sRGB",
            "equation": (
                "t = clip((c - c_min)/(c_max - c_min), 0, 1); s = t**gamma; "
                "Lab = Lab_low + s*(Lab_high - Lab_low); RGB8 = round(255*sRGB(Lab))"
            ),
            "target_min": self.target_min,
            "target_max": self.target_max,
            "gamma": self.gamma,
            "lab_low": self.lab_low.tolist(),
            "lab_high": self.lab_high.tolist(),
            "rgb8_at_target_min": self.rgb8(self.target_min).tolist(),
            "rgb8_at_target_max": self.rgb8(self.target_max).tolist(),
        }


class CalibrationTableMapping(ColorMapping):
    """Piecewise-linear interpolation through (target, L*, a*, b*) calibration points.

    For future use with real assay images and independently measured reference
    values. Targets must be strictly increasing and L* strictly monotonic.
    Values outside the table are clamped to the end points.
    """

    def __init__(self, targets, labs, mapping_id="calibration_table_v1", source="unspecified"):
        self.targets = np.asarray(targets, dtype=np.float64)
        self.labs = np.asarray(labs, dtype=np.float64)
        if self.targets.ndim != 1 or len(self.targets) < 2 or self.labs.shape != (len(self.targets), 3):
            raise ConfigError("calibration table needs >= 2 rows of (target, L, a, b)")
        if not np.all(np.diff(self.targets) > 0):
            raise ConfigError("calibration targets must be strictly increasing")
        self.mapping_id = mapping_id
        self.source = source
        self.target_min = float(self.targets[0])
        self.target_max = float(self.targets[-1])
        self._check()

    @classmethod
    def from_csv(cls, path: str | Path, mapping_id: str = "calibration_table_v1") -> "CalibrationTableMapping":
        import pandas as pd

        df = pd.read_csv(path).sort_values("target_hb_g_dl")
        return cls(df["target_hb_g_dl"].to_numpy(), df[["L", "a", "b"]].to_numpy(), mapping_id, Path(path).name)

    def lab(self, target) -> np.ndarray:
        c = np.asarray(target, dtype=np.float64)
        return np.stack([np.interp(c, self.targets, self.labs[:, i]) for i in range(3)], axis=-1)

    def describe(self) -> dict[str, Any]:
        return {
            "type": "calibration_table",
            "mapping_id": self.mapping_id,
            "source": self.source,
            "color_space": "CIELAB (D65 white), converted to 8-bit sRGB",
            "equation": "piecewise-linear interpolation of L*, a*, b* over target",
            "targets": self.targets.tolist(),
            "labs": self.labs.tolist(),
        }


def build_mapping(m: MappingConfig, config_dir: str | None = None) -> ColorMapping:
    if m.type == "synthetic_lab_linear":
        return SyntheticLabLinearMapping(m.target_min, m.target_max, m.gamma, m.lab_low, m.lab_high, m.mapping_id)
    if m.type == "calibration_table":
        if not m.calibration_table_csv:
            raise ConfigError("mapping.calibration_table_csv is required for type 'calibration_table'")
        p = Path(m.calibration_table_csv)
        if not p.is_absolute() and config_dir:
            p = Path(config_dir) / p
        mapping = CalibrationTableMapping.from_csv(p, m.mapping_id)
        if abs(mapping.target_min - m.target_min) > 1e-9 or abs(mapping.target_max - m.target_max) > 1e-9:
            raise ConfigError("mapping.target_min/target_max must match the calibration table range")
        return mapping
    raise ConfigError(f"unknown mapping type: {m.type}")
