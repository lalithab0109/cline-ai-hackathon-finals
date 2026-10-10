"""Stage 3 (secondary, DEMONSTRATION ONLY): SVM classifier on ARTIFICIAL target bands.

No genuine classification labels exist in the data. The bands below are
equal-width slices of the synthetic target range 4-18 and carry NO clinical
meaning (they are deliberately NOT named "anemia"/"normal" etc.).

Inputs: the selected feature set PLUS the SVR's out-of-fold prediction
(``svr_pred``). Using OOF predictions on train/val avoids training the SVM on
SVR outputs that already saw the label. On test, the final SVR prediction is used.
Saved separately from the SVR (``models/hb_demo_svm.joblib``).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from . import DISCLAIMER, __version__
from . import config as C

BAND_EDGES = [4.0, 8.666667, 13.333333, 18.0]
BAND_NAMES = ["artificial_band_A_4.0-8.7", "artificial_band_B_8.7-13.3", "artificial_band_C_13.3-18.0"]


def to_band(y) -> np.ndarray:
    y = np.asarray(y, float)
    return np.clip(np.digitize(y, BAND_EDGES[1:-1]), 0, len(BAND_NAMES) - 1)


def run() -> dict:
    svr_meta = json.loads(C.SVR_META_FILE.read_text(encoding="utf-8"))
    cols = svr_meta["feature_order"]
    feats = pd.read_csv(C.FEATURES_CSV)
    oof = pd.read_csv(C.PROCESSED_DIR / "svr_oof_predictions.csv")
    test = pd.read_csv(C.PROCESSED_DIR / "svr_test_predictions.csv")
    trva = feats.merge(oof[["uid", "svr_oof_pred"]], on="uid").rename(columns={"svr_oof_pred": "svr_pred"})
    te = feats.merge(test[["uid", "svr_pred"]], on="uid")
    in_cols = cols + ["svr_pred"]
    tr, va = trva[trva["split"] == "train"], trva[trva["split"] == "val"]

    grid = {"svc__C": [0.1, 1, 10, 100], "svc__gamma": ["scale", 0.01, 0.1]}
    pipe = Pipeline([("scaler", StandardScaler()), ("svc", SVC(kernel="rbf", class_weight="balanced"))])
    gs = GridSearchCV(pipe, grid, scoring="balanced_accuracy", cv=GroupKFold(n_splits=5), n_jobs=-1)
    gs.fit(tr[in_cols].to_numpy(), to_band(tr[C.TARGET]), groups=tr["split_group"].to_numpy())
    val_pred = gs.predict(va[in_cols].to_numpy())
    final = pipe.set_params(**gs.best_params_).fit(trva[in_cols].to_numpy(), to_band(trva[C.TARGET]))
    te_pred = final.predict(te[in_cols].to_numpy())

    def cls_metrics(y_true_cont, pred):
        yt = to_band(y_true_cont)
        return {"n": int(len(yt)), "accuracy": round(accuracy_score(yt, pred), 4),
                "balanced_accuracy": round(balanced_accuracy_score(yt, pred), 4),
                "macro_f1": round(f1_score(yt, pred, average="macro"), 4),
                "confusion_matrix_rows_true_cols_pred": confusion_matrix(yt, pred, labels=[0, 1, 2]).tolist()}

    # reference: simply binning the SVR regression output
    meta = {
        "model_identifier": C.SVM_IDENTIFIER, "model_version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER + " Bands are ARTIFICIAL equal-width slices with no clinical meaning.",
        "source": "synthetic", "clinically_validated": False,
        "band_edges": BAND_EDGES, "band_names": BAND_NAMES, "input_features": in_cols,
        "hyperparameters": gs.best_params_, "cv_balanced_accuracy_train": round(gs.best_score_, 4),
        "validation_metrics": cls_metrics(va[C.TARGET], val_pred),
        "test_metrics": cls_metrics(te[C.TARGET], te_pred),
        "reference_binned_svr_test": cls_metrics(te[C.TARGET], to_band(te["svr_pred"])),
        "svr_dependency": {"svr_model": C.SVR_MODEL_FILE.name, "svr_created_utc": svr_meta["created_utc"]},
    }
    joblib.dump({"pipeline": final, "feature_order": in_cols, "metadata": meta}, C.SVM_MODEL_FILE)
    C.SVM_META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("demo SVM val:", meta["validation_metrics"])
    print("demo SVM test:", meta["test_metrics"])
    print("binned SVR test (reference):", meta["reference_binned_svr_test"])
    return meta


def main(argv=None):
    argparse.ArgumentParser(description="Train demonstration SVM on artificial bands").parse_args(argv)
    run()


if __name__ == "__main__":
    main()
