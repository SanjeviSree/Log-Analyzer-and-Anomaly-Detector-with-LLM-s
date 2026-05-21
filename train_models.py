# train_models.py
# ─────────────────────────────────────────────
# ONE-TIME training script for DeepLog + LogBERT
# Run this BEFORE launching the Streamlit app:
#   cd C:\log_anomaly_detector
#   python train_models.py
# ─────────────────────────────────────────────

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from utils.constants import LOG_SOURCE_DIR, LOG_FILES, MODELS_DIR
from utils.helpers   import ensure_dirs
from pipeline.parser  import parse_file_path
from pipeline.cleaner import run_cleaning_pipeline
from pipeline.features import run_feature_engineering


def load_all_logs() -> object:
    """Reads and merges all CSV files from C:/Logs for training."""
    import pandas as pd

    all_dfs = []
    all_log_files = (
        LOG_FILES["security"] +
        LOG_FILES["network"]  +
        LOG_FILES["firewall"] +
        LOG_FILES.get("system", [])
    )

    print(f"\n📂 Loading logs from {LOG_SOURCE_DIR}...")
    for fname in all_log_files:
        fpath = os.path.join(LOG_SOURCE_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  ⚠️  Skipping (not found): {fname}")
            continue
        try:
            df = parse_file_path(fpath)
            df["source_file"] = fname
            all_dfs.append(df)
            print(f"  ✅ Loaded {len(df):,} rows from {fname}")
        except Exception as e:
            print(f"  ❌ Failed to load {fname}: {e}")

    if not all_dfs:
        raise FileNotFoundError(
            f"No log files found in {LOG_SOURCE_DIR}. "
            "Make sure your CSV files are in C:/Logs."
        )

    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"\n✅ Total rows loaded: {len(combined):,}")
    return combined


def train():
    ensure_dirs(MODELS_DIR)

    # ── Step 1: Load + Clean + Feature Engineer ──
    raw_df = load_all_logs()

    print("\n🧹 Cleaning and parsing log templates...")
    cleaned_df = run_cleaning_pipeline(raw_df, save_name="train_cleaned")

    print("\n⚙️  Engineering features...")
    df_feat, X, y, session_labels, vocab = run_feature_engineering(cleaned_df)

    print(f"\n📊 Training data ready:")
    print(f"   Sequences : {len(X):,}")
    print(f"   Vocab size: {len(vocab)}")
    print(f"   Window    : {X.shape[1]}")

    # ── Step 2: Train DeepLog ─────────────────────
    print("\n" + "="*50)
    print("🔵 Training DeepLog (LSTM)...")
    print("="*50)
    from models.deeplog import train_deeplog
    train_deeplog(X, y, vocab_size=len(vocab))
    print("✅ DeepLog training complete!")

    # ── Step 3: Train LogBERT ─────────────────────
    print("\n" + "="*50)
    print("🟠 Training LogBERT (BERT-MLM)...")
    print("="*50)
    sequences = [row.tolist() for row in X]
    from models.logbert import train_logbert
    train_logbert(sequences)
    print("✅ LogBERT training complete!")

    # ── Done ──────────────────────────────────────
    print("\n" + "="*50)
    print("🎉 Both models trained and saved to data/models/")
    print("   Now run: streamlit run app/main.py")
    print("="*50)


if __name__ == "__main__":
    train()