import unittest

import numpy as np

from aarogya_synth import colorspace as cs
from aarogya_synth.color_mapping import CalibrationTableMapping, SyntheticLabLinearMapping, build_mapping
from aarogya_synth.config import ConfigError, MappingConfig


class TestColorMapping(unittest.TestCase):
    def setUp(self):
        self.m = build_mapping(MappingConfig())

    def test_deterministic(self):
        t = np.linspace(4, 18, 101)
        np.testing.assert_array_equal(self.m.rgb8(t), self.m.rgb8(t.copy()))

    def test_strictly_monotonic_lightness(self):
        lab = self.m.lab(np.linspace(4, 18, 1001))
        self.assertTrue(np.all(np.diff(lab[:, 0]) < 0))

    def test_quantized_lightness_non_increasing(self):
        rgb = self.m.rgb8(np.linspace(4, 18, 1401))
        lightness = cs.srgb8_to_lab(rgb)[:, 0]
        self.assertTrue(np.all(np.diff(lightness) <= 1e-9))

    def test_in_gamut_and_valid_rgb(self):
        lab = self.m.lab(np.linspace(4, 18, 1001))
        self.assertTrue(cs.in_srgb_gamut(lab, tol=1e-6).all())
        rgb = self.m.rgb8(np.linspace(4, 18, 1001))
        self.assertEqual(rgb.dtype, np.uint8)

    def test_smooth_no_jumps(self):
        rgb = self.m.rgb8(np.linspace(4, 18, 1401)).astype(int)  # 0.01 g/dL steps
        self.assertLessEqual(np.abs(np.diff(rgb, axis=0)).max(), 2)

    def test_clamps_outside_range(self):
        np.testing.assert_array_equal(self.m.rgb8(2.0), self.m.rgb8(4.0))
        np.testing.assert_array_equal(self.m.rgb8(30.0), self.m.rgb8(18.0))

    def test_out_of_gamut_rejected(self):
        with self.assertRaises(ConfigError):
            SyntheticLabLinearMapping(4, 18, 1.0, (95, 80, 90), (20, -80, -90))

    def test_lab_roundtrip(self):
        lab = self.m.lab(np.linspace(4, 18, 11))
        np.testing.assert_allclose(cs.srgb_to_lab(cs.lab_to_srgb(lab)), lab, atol=1e-6)

    def test_calibration_table_replacement(self):
        grid = np.linspace(4, 18, 8)
        cal = CalibrationTableMapping(grid, self.m.lab(grid))
        np.testing.assert_allclose(cal.lab(grid), self.m.lab(grid))
        with self.assertRaises(ConfigError):
            CalibrationTableMapping(grid[::-1], self.m.lab(grid))


if __name__ == "__main__":
    unittest.main()
