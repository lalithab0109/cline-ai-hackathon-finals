"""Aarogya Bindu synthetic colorimetric-assay dataset generator.

SYNTHETIC DATA ONLY. The concentration-to-color mapping implemented here is a
software design choice. It is NOT a clinically validated or experimentally
calibrated hemoglobin assay model.
"""

__version__ = "0.1.0"

DATASET_TYPE = "synthetic"
DISCLAIMER = (
    "Synthetic data for software prototyping only. Target values are "
    "generator-assigned simulated hemoglobin-equivalent numbers, not measured "
    "hemoglobin concentrations. The color mapping is an invented design choice "
    "with no clinical calibration."
)
