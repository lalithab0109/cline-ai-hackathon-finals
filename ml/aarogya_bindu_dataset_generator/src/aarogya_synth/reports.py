"""Visual inspection outputs and summary reports.

All figures show GENERATOR-KNOWN simulated targets. No model predictions are
made or shown here, and no accuracy figures are reported. Target values are
written only in figure captions/axes, never inside the analysed image region.

Outputs:
    previews/preview_grid.png              low / mid / high targets x clean..challenging
    reports/color_mapping_curve.png        designed mapping vs. color measured from clean images
    reports/split_target_distributions.png target histograms per split
    reports/split_summary.csv              counts and target coverage per split
    reports/augmentation_summary.csv/.md   recorded augmentation parameter statistics
    reports/dataset_summary.md             index of all of the above
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless, no display needed
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import DISCLAIMER  # noqa: E402
from . import colorspace as cs  # noqa: E402
from .color_mapping import build_mapping  # noqa: E402
from .features import load_rgb, roi_pixels  # noqa: E402
from .generate import load_dataset_config  # noqa: E402
from .manifest import read_manifest  # noqa: E402
from .splits import SPLITS  # noqa: E402

FOOTNOTE = "SYNTHETIC data - generator-assigned targets, not measurements; no model predictions shown."


def _pick_bases(df: pd.DataFrame, n_per_band: int = 2) -> list[tuple[str, str]]:
    """Pick base samples near the low / middle / high end of the target range."""
    base = df.drop_duplicates("base_sample_id").sort_values("target_hb_g_dl")
    t = base["target_hb_g_dl"].to_numpy()
    lo, hi = t.min(), t.max()
    picks = []
    for band, q in (("low", 0.0), ("middle", 0.5), ("high", 1.0)):
        goal = lo + q * (hi - lo)
        order = np.argsort(np.abs(t - goal), kind="stable")[:n_per_band]
        for i in sorted(order, key=lambda i: t[i]):
            picks.append((band, base.iloc[i]["base_sample_id"]))
    return picks


def preview_grid(root: Path, df: pd.DataFrame, variants: list[str]) -> Path:
    picks = _pick_bases(df)
    fig, axes = plt.subplots(len(picks), len(variants), figsize=(2.6 * len(variants), 2.75 * len(picks)))
    axes = np.atleast_2d(axes)
    for r, (band, bid) in enumerate(picks):
        rows = df[df["base_sample_id"] == bid].set_index("augmentation_profile")
        for c, v in enumerate(variants):
            ax = axes[r, c]
            ax.set_xticks([])
            ax.set_yticks([])
            if v in rows.index:
                ax.imshow(load_rgb(root / rows.loc[v, "relative_image_path"]))
            if r == 0:
                ax.set_title(v, fontsize=11)
            if c == 0:
                t = float(rows["target_hb_g_dl"].iloc[0])
                ax.set_ylabel(f"{band}\n{bid}\nsim. target {t:.2f} g/dL", fontsize=8)
    fig.suptitle("Aarogya Bindu synthetic preview (labels in margins only, not in images)", fontsize=12)
    fig.text(0.5, 0.005, FOOTNOTE, ha="center", fontsize=8, style="italic")
    fig.tight_layout(rect=(0, 0.015, 1, 0.98))
    out = root / "previews" / "preview_grid.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=80)
    plt.close(fig)
    return out


def mapping_curve(root: Path, df: pd.DataFrame, mapping) -> Path:
    grid = np.linspace(mapping.target_min, mapping.target_max, 300)
    lab_design = mapping.lab(grid)
    rgb_design = mapping.rgb8(grid).astype(float)
    clean = df[df["augmentation_profile"] == "clean"].sort_values("target_hb_g_dl")
    meas_rgb, meas_lab = [], []
    for r in clean.itertuples(index=False):
        px = roi_pixels(load_rgb(root / r.relative_image_path), np.asarray(json.loads(r.spot_corners_xy)))
        meas_rgb.append(np.median(px, axis=0))
        meas_lab.append(np.median(cs.srgb8_to_lab(px), axis=0))
    meas_rgb, meas_lab = np.array(meas_rgb), np.array(meas_lab)
    t = clean["target_hb_g_dl"].to_numpy()

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), gridspec_kw={"width_ratios": [1.2, 1.2, 1]})
    for i, (ch, col) in enumerate(zip("RGB", ("tab:red", "tab:green", "tab:blue"))):
        axes[0].plot(grid, rgb_design[:, i], color=col, lw=1.5, label=f"{ch} designed")
        axes[0].scatter(t, meas_rgb[:, i], color=col, s=10, alpha=0.6, label=f"{ch} measured (clean)")
    axes[0].set(xlabel="simulated target_hb_g_dl", ylabel="8-bit value", title="sRGB vs simulated target")
    axes[0].legend(fontsize=7, ncol=2)
    for i, (ch, col) in enumerate(zip(("L*", "a*", "b*"), ("k", "tab:pink", "tab:olive"))):
        axes[1].plot(grid, lab_design[:, i], color=col, lw=1.5, label=f"{ch} designed")
        axes[1].scatter(t, meas_lab[:, i], color=col, s=10, alpha=0.6, label=f"{ch} measured (clean)")
    axes[1].set(xlabel="simulated target_hb_g_dl", ylabel="CIELAB", title="CIELAB vs simulated target")
    axes[1].legend(fontsize=7, ncol=2)
    axes[2].imshow(mapping.rgb8(grid)[None, :, :].repeat(40, axis=0), aspect="auto",
                   extent=(grid[0], grid[-1], 0, 1))
    axes[2].set(yticks=[], xlabel="simulated target_hb_g_dl", title="designed color strip")
    fig.suptitle(f"Synthetic color mapping '{mapping.mapping_id}' - design choice, NOT a clinical calibration")
    fig.text(0.5, 0.005, FOOTNOTE, ha="center", fontsize=8, style="italic")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    out = root / "reports" / "color_mapping_curve.png"
    fig.savefig(out, dpi=90)
    plt.close(fig)
    return out


def split_reports(root: Path, df: pd.DataFrame, mapping) -> tuple[Path, Path]:
    base = df.drop_duplicates("base_sample_id")
    rows = []
    for s in SPLITS:
        sub = base[base["dataset_split"] == s]["target_hb_g_dl"]
        rows.append({"dataset_split": s, "base_samples": len(sub), "images": int((df["dataset_split"] == s).sum()),
                     "target_min": sub.min(), "target_max": sub.max(), "target_mean": round(sub.mean(), 3),
                     "target_median": sub.median(), "target_std": round(sub.std(), 3)})
    summary = pd.DataFrame(rows)
    csv_path = root / "reports" / "split_summary.csv"
    summary.to_csv(csv_path, index=False)

    bins = np.linspace(mapping.target_min, mapping.target_max, 15)
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8), sharex=True)
    for ax, s in zip(axes, SPLITS):
        sub = base[base["dataset_split"] == s]["target_hb_g_dl"]
        ax.hist(sub, bins=bins, color="tab:gray", edgecolor="k")
        ax.set(title=f"{s}: {len(sub)} base samples", xlabel="simulated target_hb_g_dl", ylabel="base samples")
    fig.suptitle("Simulated target distribution per split (base samples; each has all variants in the same split)")
    fig.text(0.5, 0.005, FOOTNOTE, ha="center", fontsize=8, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    png_path = root / "reports" / "split_target_distributions.png"
    fig.savefig(png_path, dpi=90)
    plt.close(fig)
    return csv_path, png_path


NUMERIC_AUG = ["brightness_factor", "contrast_factor", "blur_level", "defocus_radius_px", "noise_level",
               "rotation_degrees", "perspective_strength", "scale_factor", "translate_x_px", "translate_y_px",
               "print_delta_e", "apparent_delta_e_vs_clean"]


def augmentation_summary(root: Path, df: pd.DataFrame, cfg) -> Path:
    stats = df.groupby("augmentation_profile")[NUMERIC_AUG].agg(["min", "mean", "max"]).round(4)
    stats = stats.reindex([v for v in cfg.variants if v in stats.index])
    stats.to_csv(root / "reports" / "augmentation_summary.csv")
    shadow = df.assign(has_shadow=~df["shadow_profile"].str.contains('"none"')) \
        .groupby("augmentation_profile")["has_shadow"].mean()
    illum = df["illumination_profile"].map(lambda s: json.loads(s)["type"])
    illum_counts = pd.crosstab(df["augmentation_profile"], illum)
    lines = ["# Augmentation summary", "", f"> {DISCLAIMER}", "",
             "Recorded per-image parameters (from manifest.csv), min / mean / max per profile.", "",
             "Important: brightness, contrast, white balance, illumination and shadows change the *apparent* "
             "spot color while the label is unchanged (`apparent_delta_e_vs_clean`). This simulates an "
             "uncalibrated phone camera; without reference patches these shifts cannot be fully corrected.", ""]
    lines.append("| profile | " + " | ".join(NUMERIC_AUG) + " |")
    lines.append("|---" * (len(NUMERIC_AUG) + 1) + "|")
    for prof in stats.index:
        cells = [f"{stats.loc[prof, (c, 'min')]:g} / {stats.loc[prof, (c, 'mean')]:g} / {stats.loc[prof, (c, 'max')]:g}"
                 for c in NUMERIC_AUG]
        lines.append(f"| {prof} | " + " | ".join(cells) + " |")
    lines += ["", "Fraction of images with a soft shadow:", ""]
    lines += [f"- {p}: {shadow.get(p, 0):.2f}" for p in cfg.variants]
    lines += ["", "Illumination profile types (image counts):", "", "```", illum_counts.to_string(), "```", "",
              "Configured ranges per profile:", "", "```json",
              json.dumps({k: v for k, v in cfg.to_dict()["profiles"].items() if k in cfg.variants}, indent=1), "```"]
    out = root / "reports" / "augmentation_summary.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def generate_reports(dataset_dir: str | Path) -> list[Path]:
    root = Path(dataset_dir)
    cfg, raw = load_dataset_config(root)
    mapping = build_mapping(cfg.mapping, cfg.config_dir)
    df = read_manifest(root)
    (root / "reports").mkdir(exist_ok=True)
    outs = [preview_grid(root, df, cfg.variants), mapping_curve(root, df, mapping),
            *split_reports(root, df, mapping), augmentation_summary(root, df, cfg)]
    pd.DataFrame(mapping.table()).to_csv(root / "reports" / "color_mapping_table.csv", index=False)
    outs.append(root / "reports" / "color_mapping_table.csv")
    val = root / "reports" / "validation_report.md"
    lines = ["# Dataset summary", "", f"> {DISCLAIMER}", "",
             f"- images: {len(df)}; base samples: {df['base_sample_id'].nunique()}; "
             f"variants per base sample: {', '.join(cfg.variants)}",
             f"- simulated target range: {df['target_hb_g_dl'].min():.2f} - {df['target_hb_g_dl'].max():.2f} g/dL "
             f"(configured {cfg.mapping.target_min} - {cfg.mapping.target_max})",
             f"- mapping: `{mapping.mapping_id}` - {raw['mapping_description'].get('equation', '')}",
             f"- generation batches: {len(raw.get('batches', []))}", "",
             "Targets in these reports are generator-known simulated values. No model has been trained or "
             "evaluated here; no accuracy figures are reported. A random synthetic test split does not "
             "demonstrate clinical validity or generalization to real assay chemistry.", "",
             "## Files", ""]
    lines += [f"- `{p.relative_to(root).as_posix()}`" for p in outs]
    lines.append(f"- `reports/validation_report.md` {'(present)' if val.exists() else '(run `validate` to create)'}")
    (root / "reports" / "dataset_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return outs
