"""Stage 2: train the SVR regressor (primary model) and baselines.

Protocol (no test-set peeking):
    1. For each (feature set x kernel) candidate, tune hyper-parameters with
       GridSearchCV + GroupKFold(5) on TRAIN only (groups = split_group).
    2. Score each tuned candidate once on VAL; select the lowest VAL MAE.
    3. Baselines (DummyRegressor mean, LinearRegression) are fit on TRAIN and
       scored on VAL for comparison.
    4. Refit the selected configuration on TRAIN+VAL and evaluate on TEST once.
    5. Out-of-fold predictions on TRAIN+VAL (GroupKFold) are saved for the
       demonstration SVM and to derive an empirical error band.
Images that failed preprocessing are excluded from training and reported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV, GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from . import DISCLAIMER, __version__
from . import config as C
from .feature_extraction import FEATURE_SETS
from .metrics import regression_metrics

GRIDS = {
    "linear": {"svr__C": [0.1, 1, 10, 100], "svr__epsilon": [0.05, 0.1, 0.25]},
    "rbf": {"svr__C": [1, 10, 100, 1000], "svr__gamma": ["scale", 0.01, 0.03, 0.1],
            "svr__epsilon": [0.05, 0.1, 0.25]},
}
N_FOLDS = 5


def make_svr(kernel: str) -> Pipeline:
    return Pipeline([("scaler", StandardScaler()), ("svr", SVR(kernel=kernel))])


def load_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(C.FEATURES_CSV)
    return df[df["pre_status"] == "ok"].reset_index(drop=True), df[df["pre_status"] != "ok"].reset_index(drop=True)


def dataset_fingerprint() -> str:
    h = hashlib.sha256()
    for p in (C.FEATURES_CSV, C.SPLITS_CSV, C.SOURCES_FILE):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def group_kfold(n_groups: int) -> GroupKFold:
    return GroupKFold(n_splits=min(N_FOLDS, n_groups))


def run() -> dict:
    C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    df, failed = load_features()
    tr, va, te = (df[df["split"] == s] for s in ("train", "val", "test"))
    y_tr, y_va, y_te = tr[C.TARGET].to_numpy(), va[C.TARGET].to_numpy(), te[C.TARGET].to_numpy()
    print(f"usable images: train {len(tr)}, val {len(va)}, test {len(te)}; excluded (preprocessing failed): {len(failed)}")

    candidates = []
    for fs_name, cols in FEATURE_SETS.items():
        for kernel, grid in GRIDS.items():
            gs = GridSearchCV(make_svr(kernel), grid, scoring="neg_mean_absolute_error",
                              cv=group_kfold(tr["split_group"].nunique()), n_jobs=-1, refit=True)
            gs.fit(tr[cols].to_numpy(), y_tr, groups=tr["split_group"].to_numpy())
            val_m = regression_metrics(y_va, gs.predict(va[cols].to_numpy()))
            candidates.append({"name": f"svr_{kernel}__{fs_name}", "feature_set": fs_name, "kernel": kernel,
                               "best_params": gs.best_params_, "cv_mae_train": round(-gs.best_score_, 4),
                               "val": val_m})
            print(f"  {candidates[-1]['name']:<28} CV MAE {-gs.best_score_:.3f} | VAL MAE {val_m['mae']:.3f} "
                  f"R2 {val_m['r2']} | {gs.best_params_}")
    baselines = {}
    for name, model, cols in [("dummy_mean", DummyRegressor(strategy="mean"), FEATURE_SETS["normalized"]),
                              ("linear_regression__raw_color", make_lr(), FEATURE_SETS["raw_color"]),
                              ("linear_regression__normalized", make_lr(), FEATURE_SETS["normalized"])]:
        model.fit(tr[cols].to_numpy(), y_tr)
        baselines[name] = {"val": regression_metrics(y_va, model.predict(va[cols].to_numpy()))}
        print(f"  baseline {name:<30} VAL MAE {baselines[name]['val']['mae']:.3f}")

    best = min(candidates, key=lambda c: (c["val"]["mae"], c["name"]))
    cols = FEATURE_SETS[best["feature_set"]]
    print(f"selected on VAL MAE: {best['name']}")

    trva = pd.concat([tr, va])
    final = make_svr(best["kernel"]).set_params(**best["best_params"])
    final.fit(trva[cols].to_numpy(), trva[C.TARGET].to_numpy())
    test_pred = final.predict(te[cols].to_numpy())
    test_m = regression_metrics(y_te, test_pred)
    for name, model, bcols in [("dummy_mean", DummyRegressor(strategy="mean"), cols),
                               ("linear_regression__" + best["feature_set"], make_lr(), cols)]:
        model.fit(trva[bcols].to_numpy(), trva[C.TARGET].to_numpy())
        baselines.setdefault(name, {})["test"] = regression_metrics(y_te, model.predict(te[bcols].to_numpy()))
    print(f"TEST (evaluated once): {test_m}")

    oof = cross_val_predict(clone(final), trva[cols].to_numpy(), trva[C.TARGET].to_numpy(),
                            groups=trva["split_group"].to_numpy(), cv=group_kfold(trva["split_group"].nunique()))
    oof_abs = np.abs(oof - trva[C.TARGET].to_numpy())
    pd.DataFrame({"uid": trva["uid"], "split": trva["split"], "split_group": trva["split_group"],
                  C.TARGET: trva[C.TARGET], "svr_oof_pred": oof}).to_csv(C.PROCESSED_DIR / "svr_oof_predictions.csv",
                                                                         index=False)
    pd.DataFrame({"uid": te["uid"], C.TARGET: y_te, "svr_pred": test_pred}).to_csv(
        C.PROCESSED_DIR / "svr_test_predictions.csv", index=False)

    q_train = df[df["split"].isin(["train", "val"])]
    meta = {
        "model_identifier": C.MODEL_IDENTIFIER, "model_version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER, "source": "synthetic", "clinically_validated": False,
        "target": C.TARGET, "unit": C.TARGET_UNIT, "estimator": f"StandardScaler + SVR(kernel={best['kernel']})",
        "selected_candidate": best["name"], "hyperparameters": best["best_params"],
        "feature_set": best["feature_set"], "feature_order": cols,
        "training_target_range": [float(trva[C.TARGET].min()), float(trva[C.TARGET].max())],
        "feature_ranges_train": {c: [float(q_train[c].min()), float(q_train[c].max())] for c in cols},
        "oof_abs_error_quantiles": {"p50": float(np.quantile(oof_abs, 0.5)), "p80": float(np.quantile(oof_abs, 0.8)),
                                    "p90": float(np.quantile(oof_abs, 0.9)), "p95": float(np.quantile(oof_abs, 0.95))},
        "oof_metrics_train_val": regression_metrics(trva[C.TARGET], oof),
        "dataset": {"fingerprint": dataset_fingerprint(), "sources": sorted(df["source"].unique().tolist()),
                    "n_train": len(tr), "n_val": len(va), "n_test": len(te),
                    "n_excluded_preprocessing_failed": len(failed), "split_seed": C.SPLIT_SEED},
        "selection": {"protocol": "GroupKFold(5) grid search on train; pick lowest val MAE; refit train+val; "
                                  "test evaluated once", "candidates": candidates, "baselines": baselines},
        "validation_metrics": best["val"], "test_metrics": test_m,
        "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                        "numpy": np.__version__, "pandas": pd.__version__},
    }
    joblib.dump({"pipeline": final, "feature_order": cols, "metadata": meta}, C.SVR_MODEL_FILE)
    C.SVR_META_FILE.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"saved {C.SVR_MODEL_FILE.name} and {C.SVR_META_FILE.name}")
    return meta


def make_lr() -> Pipeline:
    return Pipeline([("scaler", StandardScaler()), ("lr", LinearRegression())])


def main(argv=None):
    argparse.ArgumentParser(description="Train SVR + baselines").parse_args(argv)
    run()


if __name__ == "__main__":
    main()
