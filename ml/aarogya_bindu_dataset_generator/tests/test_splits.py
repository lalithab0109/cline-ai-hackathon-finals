import unittest
from collections import Counter

import numpy as np

from aarogya_synth.config import ConfigError, SplitConfig, config_from_dict, load_config
from aarogya_synth.generate import sample_targets
from aarogya_synth.seeding import image_seed
from aarogya_synth.splits import assign_splits


class TestSplitsAndSeeds(unittest.TestCase):
    def test_counts_and_reproducibility(self):
        t = np.random.default_rng(0).uniform(4, 18, 150)
        a = assign_splits(t, SplitConfig(), 777, 0)
        self.assertEqual(a, assign_splits(t, SplitConfig(), 777, 0))
        self.assertEqual(Counter(a), Counter({"train": 105, "val": 23, "test": 22}))

    def test_append_keeps_global_fractions(self):
        cfg = SplitConfig()
        first = assign_splits(np.linspace(4, 18, 4), cfg, 7, 0)
        counts = Counter(first)
        second = assign_splits(np.linspace(4, 18, 3), cfg, 7, 1, dict(counts))
        total = counts + Counter(second)
        self.assertEqual(sum(total.values()), 7)
        self.assertGreaterEqual(total["test"], 1)
        self.assertGreaterEqual(total["val"], 1)
        big = assign_splits(np.linspace(4, 18, 50), cfg, 7, 2, {"train": 105, "val": 23, "test": 22})
        self.assertEqual(Counter(big), Counter({"train": 35, "val": 7, "test": 8}))

    def test_split_seed_independent_of_targets(self):
        cfg = load_config(None)
        t1 = sample_targets(cfg, 50, 0)
        cfg.split_seed = 12345
        np.testing.assert_array_equal(t1, sample_targets(cfg, 50, 0))  # split seed never changes targets
        self.assertNotEqual(assign_splits(t1, cfg.splits, 777, 0), assign_splits(t1, cfg.splits, 12345, 0))

    def test_stratified_coverage(self):
        t = np.linspace(4, 18, 100)
        a = np.array(assign_splits(t, SplitConfig(), 1, 0))
        for s in ("train", "val", "test"):
            sub = t[a == s]
            self.assertLess(sub.min(), 7.5)
            self.assertGreater(sub.max(), 14.5)

    def test_targets_cover_range(self):
        cfg = load_config(None)
        t = sample_targets(cfg, 140, 0)
        counts, _ = np.histogram(t, bins=14, range=(4, 18))
        self.assertTrue((counts >= 8).all())
        self.assertTrue(((t >= 4) & (t <= 18)).all())

    def test_image_seeds_unique(self):
        seeds = {image_seed(1, b, i, v, a) for b in range(2) for i in range(200) for v in range(4) for a in range(2)}
        self.assertEqual(len(seeds), 2 * 200 * 4 * 2)

    def test_config_rejects_unknown_keys_and_bad_values(self):
        with self.assertRaises(ConfigError):
            config_from_dict({"num_base_sample": 10})
        with self.assertRaises(ConfigError):
            config_from_dict({"splits": {"train": 0.9, "val": 0.2, "test": 0.1}})
        with self.assertRaises(ConfigError):
            config_from_dict({"variants": ["mild"]})


if __name__ == "__main__":
    unittest.main()
