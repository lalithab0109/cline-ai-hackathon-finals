"""Project paths and fixed constants. All paths are relative to the project root."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SPLITS_DIR = DATA_DIR / "splits"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"
SOURCES_FILE = DATA_DIR / "sources.json"

# Dataset contract
TARGET = "target_hb_g_dl"
TARGET_UNIT = "g/dL"
EXPECTED_SIZE = (512, 512)  # (width, height)
DOCUMENTED_TARGET_RANGE = (4.0, 18.0)

# Reproducibility
SPLIT_SEED = 2026
CV_SEED = 7
SPLIT_FRACTIONS = {"train": 0.70, "val": 0.15, "test": 0.15}

# Artifacts
SVR_MODEL_FILE = MODELS_DIR / "hb_svr.joblib"
SVR_META_FILE = MODELS_DIR / "hb_svr_metadata.json"
SVM_MODEL_FILE = MODELS_DIR / "hb_demo_svm.joblib"
SVM_META_FILE = MODELS_DIR / "hb_demo_svm_metadata.json"
FEATURES_CSV = PROCESSED_DIR / "features.csv"
DATASET_CSV = PROCESSED_DIR / "dataset_index.csv"
SPLITS_CSV = SPLITS_DIR / "splits.csv"

MODEL_IDENTIFIER = "aarogya-bindu-hb-svr"
SVM_IDENTIFIER = "aarogya-bindu-hb-demo-svm"
