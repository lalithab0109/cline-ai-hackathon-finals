"""Configuration model, loading, validation and hashing.

Configuration is stored as JSON (see ``configs/pilot.json``). The fully resolved
configuration is written to ``generation_config.json`` in each dataset.

Coordinate convention (used everywhere in this project):
    * origin (0, 0) is the top-left corner of the image
    * x increases to the right (columns), y increases downward (rows)
    * pixel (col=i, row=j) covers the continuous area [i, i+1) x [j, j+1)
    * the clean reaction spot covers columns spot_x .. spot_x+spot_width-1 and
      rows spot_y .. spot_y+spot_height-1
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised for invalid or incompatible configuration."""


Range = tuple[float, float]


@dataclass
class ImageConfig:
    width: int = 512
    height: int = 512
    background_rgb: tuple[int, int, int] = (255, 255, 255)
    spot_x: int = 176  # top-left column of the spot in the clean image
    spot_y: int = 196  # top-left row of the spot in the clean image
    spot_width: int = 160
    spot_height: int = 120


@dataclass
class MappingConfig:
    type: str = "synthetic_lab_linear"
    mapping_id: str = "synthetic_lab_linear_v1"
    target_min: float = 4.0
    target_max: float = 18.0
    gamma: float = 1.0
    lab_low: tuple[float, float, float] = (86.0, 8.0, 38.0)
    lab_high: tuple[float, float, float] = (38.0, 45.0, 28.0)
    # Only for type == "calibration_table": CSV with columns target_hb_g_dl,L,a,b
    # (path relative to the config file's folder).
    calibration_table_csv: str | None = None


@dataclass
class AugmentationProfile:
    """Ranges for one severity level. Defaults are the 'mild' profile."""

    # print / paper variation
    print_delta_e_max: float = 0.75  # random Lab offset of the printed spot (CIE76)
    spot_gradient_max_delta_l: float = 1.0  # L* change across the spot
    edge_softness_sigma_px: Range = (0.3, 0.8)
    edge_darkening_max: float = 0.02  # darker rim (coffee-ring-like), fraction
    paper_texture_sigma: Range = (0.5, 1.0)  # 8-bit units, smooth paper grain
    # geometry
    rotation_max_deg: float = 2.0
    perspective_max: float = 0.01  # corner displacement as a fraction of image size
    scale_max: float = 0.03  # scale in [1 - scale_max, 1 + scale_max]
    translate_max_px: float = 10.0
    # lighting
    illumination_amplitude_max: float = 0.05
    shadow_probability: float = 0.1
    shadow_strength: Range = (0.03, 0.10)
    # optics
    blur_sigma: Range = (0.0, 0.6)
    defocus_probability: float = 0.0
    defocus_radius: Range = (1.0, 1.5)
    # camera / ISP
    white_balance_max: float = 0.03  # per-channel gain in [1 - wb, 1 + wb]
    brightness: Range = (0.95, 1.05)
    contrast: Range = (0.95, 1.05)
    noise_sigma: Range = (0.0, 2.0)  # 8-bit units


def default_profiles() -> dict[str, AugmentationProfile]:
    return {
        "mild": AugmentationProfile(),
        "moderate": AugmentationProfile(
            print_delta_e_max=1.5, spot_gradient_max_delta_l=2.0, edge_softness_sigma_px=(0.5, 1.5),
            edge_darkening_max=0.04, paper_texture_sigma=(1.0, 2.0), rotation_max_deg=5.0,
            perspective_max=0.025, scale_max=0.06, translate_max_px=25.0,
            illumination_amplitude_max=0.12, shadow_probability=0.3, shadow_strength=(0.05, 0.20),
            blur_sigma=(0.5, 1.3), defocus_probability=0.2, defocus_radius=(1.0, 2.0),
            white_balance_max=0.07, brightness=(0.88, 1.12), contrast=(0.90, 1.10),
            noise_sigma=(2.0, 5.0),
        ),
        "challenging": AugmentationProfile(
            print_delta_e_max=2.5, spot_gradient_max_delta_l=3.5, edge_softness_sigma_px=(0.8, 2.5),
            edge_darkening_max=0.06, paper_texture_sigma=(1.5, 3.0), rotation_max_deg=10.0,
            perspective_max=0.045, scale_max=0.10, translate_max_px=45.0,
            illumination_amplitude_max=0.22, shadow_probability=0.6, shadow_strength=(0.10, 0.35),
            blur_sigma=(1.0, 2.5), defocus_probability=0.35, defocus_radius=(1.5, 3.0),
            white_balance_max=0.12, brightness=(0.78, 1.22), contrast=(0.80, 1.20),
            noise_sigma=(4.0, 10.0),
        ),
    }


@dataclass
class GenerationChecks:
    max_attempts: int = 5  # regeneration attempts for an image that fails checks
    min_margin_px: int = 16  # transformed spot corners must stay this far inside the frame
    require_detectable_spot: bool = True
    min_detection_iou: float = 0.6  # detected ROI vs. ground-truth spot polygon
    min_spot_paper_delta_e: float = 10.0


@dataclass
class SplitConfig:
    train: float = 0.70
    val: float = 0.15
    test: float = 0.15
    stratify_bins: int = 5


@dataclass
class GeneratorConfig:
    num_base_samples: int = 150
    generation_seed: int = 20261010
    split_seed: int = 777
    target_decimals: int = 2
    variants: list[str] = field(default_factory=lambda: ["clean", "mild", "moderate", "challenging"])
    image: ImageConfig = field(default_factory=ImageConfig)
    mapping: MappingConfig = field(default_factory=MappingConfig)
    profiles: dict[str, AugmentationProfile] = field(default_factory=default_profiles)
    splits: SplitConfig = field(default_factory=SplitConfig)
    checks: GenerationChecks = field(default_factory=GenerationChecks)
    config_dir: str | None = None  # folder of the config file, for relative paths

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("config_dir", None)
        return _jsonable(d)

    def core_dict(self) -> dict[str, Any]:
        """Settings that must match when appending batches to an existing dataset."""
        d = self.to_dict()
        for k in ("num_base_samples", "generation_seed", "split_seed"):
            d.pop(k)
        return d

    def core_hash(self) -> str:
        blob = json.dumps(self.core_dict(), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def validate(self) -> None:
        _validate(self)


def _validate(cfg: GeneratorConfig) -> None:
    im = cfg.image
    if im.width < 64 or im.height < 64:
        raise ConfigError("image width/height must be >= 64")
    if im.spot_width < 8 or im.spot_height < 8:
        raise ConfigError("spot dimensions must be >= 8 px")
    if im.spot_x < 0 or im.spot_x + im.spot_width > im.width:
        raise ConfigError("spot_x/spot_width place the spot outside the image")
    if im.spot_y < 0 or im.spot_y + im.spot_height > im.height:
        raise ConfigError("spot_y/spot_height place the spot outside the image")
    if len(im.background_rgb) != 3 or any(not 0 <= c <= 255 for c in im.background_rgb):
        raise ConfigError("background_rgb must be three values in 0..255")
    if cfg.num_base_samples < 1:
        raise ConfigError("num_base_samples must be >= 1")
    if not 0 <= cfg.target_decimals <= 4:
        raise ConfigError("target_decimals must be in 0..4")
    m = cfg.mapping
    if not m.target_max > m.target_min:
        raise ConfigError("mapping.target_max must be greater than target_min")
    if m.gamma <= 0:
        raise ConfigError("mapping.gamma must be > 0")
    if not cfg.variants or cfg.variants[0] != "clean":
        raise ConfigError("variants must start with 'clean'")
    if len(set(cfg.variants)) != len(cfg.variants):
        raise ConfigError("variants must be unique")
    for v in cfg.variants[1:]:
        if v not in cfg.profiles:
            raise ConfigError(f"variant '{v}' has no augmentation profile")
    s = cfg.splits
    if min(s.train, s.val, s.test) < 0 or abs(s.train + s.val + s.test - 1.0) > 1e-6:
        raise ConfigError("split fractions must be non-negative and sum to 1")
    if s.stratify_bins < 1:
        raise ConfigError("splits.stratify_bins must be >= 1")
    for name, p in cfg.profiles.items():
        for f in fields(p):
            val = getattr(p, f.name)
            if isinstance(val, tuple):
                if len(val) != 2 or val[0] > val[1]:
                    raise ConfigError(f"profiles.{name}.{f.name}: range must be [low, high], low <= high")
                if val[0] < 0 or (f.name in ("brightness", "contrast") and val[0] == 0):
                    raise ConfigError(f"profiles.{name}.{f.name}: invalid lower bound")
            elif val < 0:
                raise ConfigError(f"profiles.{name}.{f.name}: must be >= 0")
        if p.shadow_probability > 1 or p.defocus_probability > 1:
            raise ConfigError(f"profiles.{name}: probabilities must be in [0, 1]")
        if p.shadow_strength[1] >= 1 or p.illumination_amplitude_max >= 1 or p.white_balance_max >= 1:
            raise ConfigError(f"profiles.{name}: shadow/illumination/white-balance must be < 1")
    if cfg.checks.max_attempts < 1:
        raise ConfigError("checks.max_attempts must be >= 1")


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def _build(cls, data: dict[str, Any], where: str):
    """Instantiate dataclass ``cls`` from a dict, rejecting unknown keys."""
    data = {k: v for k, v in data.items() if not k.startswith("_")}
    unknown = set(data) - {f.name for f in fields(cls)}
    if unknown:
        raise ConfigError(f"unknown config keys in '{where}': {sorted(unknown)}")
    return cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in data.items()})


# Informational keys written into generation_config.json; ignored when re-loading.
_INFO_KEYS = ("config_hash", "generator_version", "dataset_type", "mapping_description",
              "disclaimer", "coordinate_convention", "library_versions", "batches", "config_dir")


def config_from_dict(data: dict[str, Any], config_dir: str | None = None) -> GeneratorConfig:
    data = {k: v for k, v in copy.deepcopy(data).items() if not k.startswith("_") and k not in _INFO_KEYS}
    cfg = GeneratorConfig()
    for key in ("image", "mapping", "splits", "checks"):
        if key in data:
            merged = {**asdict(getattr(cfg, key)), **data.pop(key)}
            setattr(cfg, key, _build(type(getattr(cfg, key)), merged, key))
    if "profiles" in data:
        profiles = dict(cfg.profiles)
        for name, pdata in data.pop("profiles").items():
            base = asdict(profiles.get(name, AugmentationProfile()))
            base.update(pdata)
            profiles[name] = _build(AugmentationProfile, base, f"profiles.{name}")
        cfg.profiles = profiles
    unknown = set(data) - {f.name for f in fields(GeneratorConfig)}
    if unknown:
        raise ConfigError(f"unknown top-level config keys: {sorted(unknown)}")
    for k, v in data.items():
        setattr(cfg, k, list(v) if k == "variants" else v)
    cfg.config_dir = config_dir
    cfg.validate()
    return cfg


def load_config(path: str | Path | None) -> GeneratorConfig:
    if path is None:
        cfg = GeneratorConfig()
        cfg.validate()
        return cfg
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return config_from_dict(json.load(fh), config_dir=str(path.resolve().parent))
