"""Deterministic seed derivation.

All randomness is derived from two user-facing root seeds:

* ``generation_seed`` -> target sampling and per-image augmentation seeds
* ``split_seed``      -> train/val/test assignment

Independent streams are obtained with ``numpy.random.SeedSequence`` spawn keys,
so changing the split seed never changes any image, and vice versa.

The per-image integer seed recorded in ``manifest.csv`` (``random_seed``) is
sufficient on its own to re-render that image:
``numpy.random.default_rng(random_seed)``.
"""

from __future__ import annotations

import numpy as np

STREAM_TARGETS = 1
STREAM_IMAGES = 2
STREAM_SPLITS = 3


def derive_seed(root_seed: int, *keys: int) -> int:
    """Return a reproducible 32-bit integer seed derived from ``root_seed`` and ``keys``."""
    ss = np.random.SeedSequence(int(root_seed), spawn_key=tuple(int(k) for k in keys))
    return int(ss.generate_state(1, dtype=np.uint32)[0])


def target_rng(generation_seed: int, batch_index: int) -> np.random.Generator:
    return np.random.default_rng(derive_seed(generation_seed, STREAM_TARGETS, batch_index))


def split_rng(split_seed: int, batch_index: int) -> np.random.Generator:
    return np.random.default_rng(derive_seed(split_seed, STREAM_SPLITS, batch_index))


def image_seed(
    generation_seed: int, batch_index: int, base_index: int, variant_index: int, attempt: int
) -> int:
    return derive_seed(generation_seed, STREAM_IMAGES, batch_index, base_index, variant_index, attempt)
