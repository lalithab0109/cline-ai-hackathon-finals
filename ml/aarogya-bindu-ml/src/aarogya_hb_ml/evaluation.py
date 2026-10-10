"""Stage 4: evaluation report for the saved SVR on the held-out TEST split.

Produces reports/evaluation.json, reports/evaluation.md and plots:
    pred_vs_true.png, residuals.png, error_by_profile.png, error_by_target_range.png,
    error_vs_conditions.png
Breakdowns: augmentation profile, target range, brightness, blur, noise,
rotation, perspective, apparent color shift, contributor source.
"""

from __future__ import annotations

import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import DISCLAIMER  # noqa: E402
from . import config as C  # noqa: E402
from .metrics import regression_metrics  # noqa: E402

CONDITIONS = {
    "brightness_factor": "brightness factor",
    "blur_level": "blur level",
    "noise_level": "noise level",
    "rotation_degrees": "rotation (deg)",
    "perspective_strength": "perspective strength",
    "apparent_delta_e_vs_clean": "apparent dE vs clean",
}


def _breakdown(df: pd.DataFrame, by: str) -> dict:
    out = {}
    for k, g in df.groupby(by, observed=True):
        if len(g) >= 2:
            out[str(k)] = regression_metrics(g[C.TARGET], g["svr_pred"])
    return out


def _cond_bins(s: pd.Series, name: str) -> pd.Series:
    if name == "rotation_degrees":
        s = s.abs()
    try:
        return pd.qcut(s, q=3, duplicates="drop").astype(str)
    except ValueError:
        return s.astype(str)


def run() -> dict:
    meta = json.loads(C.SVR_META_FILE.read_text(encoding="utf-8"))
    feats = pd.read_csv(C.FEATURES_CSV)
    preds = pd.read_csv(C.PROCESSED_DIR / "svr_test_predictions.csv")
    te = feats.merge(preds[["uid", "svr_pred"]], on="uid")
    te["abs_err"] = (te["svr_pred"] - te[C.TARGET]).abs()
    te["target_range"] = pd.cut(te[C.TARGET], [4, 7, 10, 13, 16, 18], include_lowest=True).astype(str)
    excluded = feats[(feats["split"] == "test") & (feats["pre_status"] != "ok")]

    report = {"disclaimer": DISCLAIMER, "model": meta["selected_candidate"],
              "hyperparameters": meta["hyperparameters"],
              "test_overall": regression_metrics(te[C.TARGET], te["svr_pred"]),
              "test_excluded_by_quality_gate": excluded[["uid", "augmentation_profile", "pre_issues"]].to_dict("records"),
              "validation_selected": meta["validation_metrics"],
              "baselines": meta["selection"]["baselines"],
              "candidates_val": {c["name"]: c["val"] for c in meta["selection"]["candidates"]},
              "by_profile": _breakdown(te, "augmentation_profile"),
              "by_target_range": _breakdown(te, "target_range"),
              "by_source": _breakdown(te, "source"),
              "by_condition_tercile": {}}
    for col in CONDITIONS:
        if te[col].notna().sum() > 3:
            te[f"_{col}"] = _cond_bins(te[col], col)
            report["by_condition_tercile"][col] = _breakdown(te, f"_{col}")
    report["worst_10"] = te.nlargest(10, "abs_err")[["uid", "augmentation_profile", C.TARGET, "svr_pred", "abs_err",
                                                     "brightness_factor", "blur_level", "noise_level",
                                                     "rotation_degrees"]].round(3).to_dict("records")
    _plots(te, meta)
    (C.REPORTS_DIR / "evaluation.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    _markdown(report)
    print(json.dumps({"test_overall": report["test_overall"],
                      "by_profile": {k: v["mae"] for k, v in report["by_profile"].items()}}, indent=2))
    return report


def _plots(te: pd.DataFrame, meta: dict) -> None:
    out = C.REPORTS_DIR
    colors = {"clean": "tab:green", "mild": "tab:blue", "moderate": "tab:orange", "challenging": "tab:red"}
    fig, ax = plt.subplots(figsize=(6, 6))
    for prof, g in te.groupby("augmentation_profile"):
        ax.scatter(g[C.TARGET], g["svr_pred"], s=18, alpha=0.8, label=prof, color=colors.get(prof))
    lims = [3.5, 18.5]
    ax.plot(lims, lims, "k--", lw=1)
    ax.set(xlim=lims, ylim=lims, xlabel="true simulated target (g/dL)", ylabel="predicted (g/dL)",
           title=f"TEST: {meta['selected_candidate']}\nSYNTHETIC - not for medical use")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "pred_vs_true.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(te[C.TARGET], te["svr_pred"] - te[C.TARGET], s=14,
               c=[colors.get(p, "k") for p in te["augmentation_profile"]])
    ax.axhline(0, color="k", lw=1)
    ax.set(xlabel="true simulated target (g/dL)", ylabel="residual (pred - true)", title="TEST residuals (synthetic)")
    fig.tight_layout()
    fig.savefig(out / "residuals.png", dpi=120)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    order = [p for p in ["clean", "mild", "moderate", "challenging"] if p in set(te["augmentation_profile"])]
    axes[0].boxplot([te.loc[te["augmentation_profile"] == p, "abs_err"] for p in order], tick_labels=order)
    axes[0].set(title="abs error by augmentation profile (TEST)", ylabel="|error| g/dL")
    rng = sorted(te["target_range"].unique(), key=lambda s: float(s.strip("([").split(",")[0]))
    axes[1].boxplot([te.loc[te["target_range"] == r, "abs_err"] for r in rng], tick_labels=rng)
    axes[1].set(title="abs error by target range (TEST)")
    axes[1].tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(out / "error_by_profile_and_range.png", dpi=120)
    plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, (col, label) in zip(axes.ravel(), CONDITIONS.items()):
        x = te[col].abs() if col == "rotation_degrees" else te[col]
        ax.scatter(x, te["abs_err"], s=12, alpha=0.7)
        ax.set(xlabel=label if col != "rotation_degrees" else "|rotation| (deg)", ylabel="|error| g/dL")
    fig.suptitle("TEST absolute error vs augmentation conditions (synthetic)")
    fig.tight_layout()
    fig.savefig(out / "error_vs_conditions.png", dpi=120)
    plt.close(fig)


def _markdown(r: dict) -> None:
    def row(name, m):
        return f"| {name} | {m['n']} | {m['mae']} | {m['rmse']} | {m['r2']} | {m['bias']} | {m['within_1_0']} |"

    hdr = ["| subset | n | MAE | RMSE | R2 | bias | within 1.0 |", "|---|---|---|---|---|---|---|"]
    lines = ["# Evaluation report (TEST split, evaluated once)", "", f"> {r['disclaimer']}", "",
             f"Model: `{r['model']}` {r['hyperparameters']}", "", "## Overall", ""] + hdr
    lines.append(row("TEST selected SVR", r["test_overall"]))
    lines.append(row("VAL selected SVR", r["validation_selected"]))
    for name, b in r["baselines"].items():
        for split in ("val", "test"):
            if split in b:
                lines.append(row(f"{split.upper()} baseline {name}", b[split]))
    lines += ["", "## Candidates (validation)", ""] + hdr + [row(k, v) for k, v in r["candidates_val"].items()]
    for title, key in [("By augmentation profile", "by_profile"), ("By target range", "by_target_range"),
                       ("By contributor source", "by_source")]:
        lines += ["", f"## {title}", ""] + hdr + [row(k, v) for k, v in r[key].items()]
    for col, d in r["by_condition_tercile"].items():
        lines += ["", f"## By {col} (terciles)", ""] + hdr + [row(k, v) for k, v in d.items()]
    lines += ["", "## Excluded by quality gate", "", "```", json.dumps(r["test_excluded_by_quality_gate"], indent=2),
              "```", "", "## Worst 10 test predictions", "", "```", json.dumps(r["worst_10"], indent=2), "```",
              "", "Plots: pred_vs_true.png, residuals.png, error_by_profile_and_range.png, error_vs_conditions.png"]
    (C.REPORTS_DIR / "evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    argparse.ArgumentParser(description="Evaluate the saved SVR on the test split").parse_args(argv)
    run()


if __name__ == "__main__":
    main()
