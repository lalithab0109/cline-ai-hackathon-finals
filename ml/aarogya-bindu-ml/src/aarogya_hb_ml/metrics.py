"""Regression metrics shared by training, evaluation and tests."""

from __future__ import annotations

import numpy as np


def regression_metrics(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    err = y_pred - y_true
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return {
        "n": int(len(y_true)),
        "mae": round(float(np.mean(np.abs(err))), 4),
        "rmse": round(float(np.sqrt(np.mean(err ** 2))), 4),
        "r2": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else None,
        "bias": round(float(np.mean(err)), 4),
        "max_abs_error": round(float(np.max(np.abs(err))), 4),
        "within_0_5": round(float(np.mean(np.abs(err) <= 0.5)), 4),
        "within_1_0": round(float(np.mean(np.abs(err) <= 1.0)), 4),
    }
