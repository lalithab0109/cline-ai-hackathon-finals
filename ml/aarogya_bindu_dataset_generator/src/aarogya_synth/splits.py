"""Reproducible, leakage-free train/val/test assignment of *base samples*.

Splitting happens on independent base samples BEFORE any augmented variants
are rendered; every variant inherits its base sample's split, so augmentations
of one base sample can never appear in different splits.

Strategy: base samples are sorted by target and grouped into ``stratify_bins``
equal-count quantile bins. Within each bin the samples are shuffled with a
generator seeded only by ``split_seed`` (and the batch index) and assigned
train/val/test by largest-remainder rounding of the configured fractions.
This keeps the target coverage of each split similar.

Appended batches (``--append``) are split independently with their own
batch-specific split stream, but their split *counts* are chosen so that the
dataset-wide fractions stay on target (see ``batch_quota``).
"""

from __future__ import annotations

import numpy as np

from .config import SplitConfig
from .seeding import split_rng

SPLITS = ("train", "val", "test")


def _allocate(n: int, fracs: tuple[float, float, float]) -> list[int]:
    raw = np.array(fracs) * n
    counts = np.floor(raw).astype(int)
    order = np.argsort(-(raw - counts), kind="stable")
    for i in order[: n - counts.sum()]:
        counts[i] += 1
    return counts.tolist()


def batch_quota(n: int, cfg: SplitConfig, existing_counts: dict[str, int] | None = None) -> list[int]:
    """Split counts for a batch of ``n`` new base samples.

    For the first batch this is a largest-remainder allocation of the fractions.
    For appended batches the quota is computed for the *whole* dataset
    (existing + new) and the existing counts are subtracted, so overall split
    fractions stay on target even when batches are small. Existing assignments
    are never changed.
    """
    fracs = (cfg.train, cfg.val, cfg.test)
    if not existing_counts:
        return _allocate(n, fracs)
    have = np.array([existing_counts.get(s, 0) for s in SPLITS])
    need = np.maximum(np.array(_allocate(int(have.sum()) + n, fracs)) - have, 0)
    while need.sum() > n:  # trim where the surplus is largest
        need[int(np.argmax(need - np.array(fracs) * n))] -= 1
    while need.sum() < n:
        need[int(np.argmax(np.array(fracs)))] += 1
    return need.tolist()


def assign_splits(targets: np.ndarray, cfg: SplitConfig, split_seed: int, batch_index: int,
                  existing_counts: dict[str, int] | None = None) -> list[str]:
    """Return one split name per base sample (same order as ``targets``)."""
    targets = np.asarray(targets, dtype=np.float64)
    n = len(targets)
    rng = split_rng(split_seed, batch_index)
    total = np.array(batch_quota(n, cfg, existing_counts), dtype=np.float64)
    # Quantile bins by target; shuffle within each bin (split_seed only).
    order = np.argsort(targets, kind="stable")
    bins = np.array_split(order, max(1, min(cfg.stratify_bins, n)))
    sequence = []
    for idx in bins:
        idx = idx.copy()
        rng.shuffle(idx)
        sequence.extend(int(i) for i in idx)
    # Proportional (systematic) interleaving: at each position give the sample
    # to the split furthest behind its quota. Exact global counts; every target
    # bin receives a near-proportional share of each split.
    out = [""] * n
    assigned = np.zeros(3)
    for pos, i in enumerate(sequence):
        deficit = total * (pos + 1) / max(n, 1) - assigned
        deficit[assigned >= total] = -np.inf
        s = int(np.argmax(deficit))
        out[i] = SPLITS[s]
        assigned[s] += 1
    return out
