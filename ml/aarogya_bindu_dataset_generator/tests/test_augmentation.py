import unittest

import numpy as np

from aarogya_synth.augmentation import render_variant
from aarogya_synth.color_mapping import build_mapping
from aarogya_synth.config import load_config
from aarogya_synth.features import detect_spot, polygon_iou
from aarogya_synth.generate import check_image


class TestAugmentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config(None)
        cls.m = build_mapping(cls.cfg.mapping)

    def test_clean_is_exact_and_seed_independent(self):
        a, _ = render_variant(self.cfg, self.m, 10.0, "clean", 1)
        b, _ = render_variant(self.cfg, self.m, 10.0, "clean", 999)
        np.testing.assert_array_equal(a, b)
        im = self.cfg.image
        spot = a[im.spot_y : im.spot_y + im.spot_height, im.spot_x : im.spot_x + im.spot_width]
        self.assertTrue((spot == self.m.rgb8(10.0)).all())
        self.assertTrue((a[0, 0] == 255).all())
        self.assertEqual(a.shape, (512, 512, 3))

    def test_same_seed_same_pixels_and_params(self):
        for v in ("mild", "moderate", "challenging"):
            a, pa = render_variant(self.cfg, self.m, 12.3, v, 42)
            b, pb = render_variant(self.cfg, self.m, 12.3, v, 42)
            np.testing.assert_array_equal(a, b)
            self.assertEqual({k: x for k, x in pa.items() if k != "spot_corners_xy"},
                             {k: x for k, x in pb.items() if k != "spot_corners_xy"})

    def test_different_seed_differs(self):
        a, _ = render_variant(self.cfg, self.m, 12.3, "moderate", 1)
        b, _ = render_variant(self.cfg, self.m, 12.3, "moderate", 2)
        self.assertFalse(np.array_equal(a, b))

    def test_variants_pass_checks_and_spot_in_frame(self):
        for seed in range(6):
            for v in ("mild", "moderate", "challenging"):
                img, p = render_variant(self.cfg, self.m, 4.0 + 2.5 * seed, v, seed)
                self.assertEqual(img.dtype, np.uint8)
                corners = np.asarray(p["spot_corners_xy"])
                self.assertTrue((corners >= self.cfg.checks.min_margin_px).all())
                self.assertTrue((corners <= 512 - self.cfg.checks.min_margin_px).all())
                self.assertGreater(polygon_iou(detect_spot(img), corners, img.shape[:2]), 0.6)
                self.assertEqual(check_image(self.cfg, img, corners), [])


if __name__ == "__main__":
    unittest.main()
