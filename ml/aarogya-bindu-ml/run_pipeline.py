"""Run the full pipeline: validate+split+features -> SVR -> demo SVM -> evaluation.

Usage:  .venv\\Scripts\\python.exe run_pipeline.py [--skip-prepare]
SYNTHETIC DEMONSTRATION ONLY - NOT FOR MEDICAL USE.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from aarogya_hb_ml import evaluation, prepare_data, train_svm, train_svr  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-prepare", action="store_true", help="reuse data/processed/features.csv")
    a = ap.parse_args()
    if not a.skip_prepare:
        print("== 1/4 dataset validation, splits, preprocessing, features ==")
        prepare_data.run()
    print("== 2/4 SVR training + baselines ==")
    train_svr.run()
    print("== 3/4 demonstration SVM (artificial bands) ==")
    train_svm.run()
    print("== 4/4 evaluation ==")
    evaluation.run()


if __name__ == "__main__":
    main()
