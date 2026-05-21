# pipeline/features.py
# ─────────────────────────────────────────────
# Feature engineering — runs after cleaner.py
# Converts cleaned DataFrame into model-ready sequences
# ─────────────────────────────────────────────

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from utils.constants import DEEPLOG_CONFIG, MIN_SEQUENCE_TOKENS
from utils.helpers import save_processed

WINDOW_SIZE = DEEPLOG_CONFIG["window_size"]


# ── Template ID Encoding ──────────────────────

def encode_template_ids(df: pd.DataFrame) -> tuple:
    """Converts string template_ids into integer codes."""
    unique_templates = df["template_id"].unique().tolist()
    vocab = {tid: idx + 1 for idx, tid in enumerate(unique_templates)}
    vocab["<UNK>"] = 0
    df = df.copy()
    df["template_code"] = df["template_id"].map(vocab).fillna(0).astype(int)
    return df, vocab


# ── Session Grouping ──────────────────────────

def group_into_sessions(df: pd.DataFrame, session_col: str = None) -> dict:
    """
    Groups log rows into sessions using 3-level priority:
      1. Explicit session column
      2. 1-hour time window buckets
      3. Fixed 50-row chunks (guaranteed fallback — always works)
    """
    codes = df["template_code"].tolist()

    # 1. Explicit session column
    if session_col and session_col in df.columns:
        groups = df.groupby(session_col)["template_code"].apply(list).to_dict()
        if any(len(v) > 1 for v in groups.values()):
            return groups

    # 2. Time-window grouping (1-hour buckets)
    if "parsed_timestamp" in df.columns:
        tmp = df.copy()
        tmp["parsed_timestamp"] = pd.to_datetime(tmp["parsed_timestamp"], errors="coerce")
        valid = tmp.dropna(subset=["parsed_timestamp"])
        if len(valid) > 10:
            valid = valid.copy()
            valid["hour_bucket"] = valid["parsed_timestamp"].dt.floor("1h")
            groups = valid.groupby("hour_bucket")["template_code"].apply(list).to_dict()
            groups = {str(k): v for k, v in groups.items() if len(v) > 1}
            if groups:
                return groups

    # 3. Fixed 50-row chunks — always works regardless of timestamps
    chunk_size = 50
    groups = {}
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i: i + chunk_size]
        if chunk:
            groups[f"chunk_{i // chunk_size}"] = chunk

    return groups if groups else {"session_0": codes}


# ── Sliding Window Sequences ──────────────────

def build_sequences(session_sequences: dict, window: int = WINDOW_SIZE) -> tuple:
    """
    Builds sliding window sequences from sessions.

    Key improvements over previous version:
    - Skips sequences with fewer than MIN_SEQUENCE_TOKENS real tokens
      (padding tokens = 0, these produce garbage anomaly scores)
    - Auto-scales window to available data
    - Works for any file size — small or large
    """
    # Flatten to measure total data
    all_codes_flat = []
    for seq in session_sequences.values():
        all_codes_flat.extend(seq)

    total_codes = len(all_codes_flat)

    if total_codes < 3:
        raise ValueError(
            f"Only {total_codes} log template(s) found after parsing. "
            "File may be empty or all rows parsed to the same template."
        )

    # Auto-scale window — never exceed data size
    usable_window = min(window, max(2, total_codes // 4))

    X, y, session_labels = [], [], []

    for session_id, seq in session_sequences.items():
        if len(seq) < 2:
            continue

        local_w = min(usable_window, len(seq) - 1)
        local_w = max(local_w, 2) if len(seq) >= 3 else 1

        for i in range(len(seq) - local_w):
            window_seq = seq[i: i + local_w]

            # ── Key fix: skip sequences with too few real tokens ──
            # Sequences that are mostly padding (0s) give unreliable
            # anomaly scores and cause normal data to be flagged
            real_tokens = sum(1 for t in window_seq if t != 0)
            if real_tokens < MIN_SEQUENCE_TOKENS:
                continue

            # Pad to usable_window width if needed
            if len(window_seq) < usable_window:
                window_seq = [0] * (usable_window - len(window_seq)) + window_seq

            X.append(window_seq)
            y.append(seq[i + local_w])
            session_labels.append(str(session_id))

    # Fallback: global flat sequence if all sessions were too short
    if not X:
        local_w = min(usable_window, len(all_codes_flat) - 1)
        local_w = max(local_w, 2)
        for i in range(len(all_codes_flat) - local_w):
            window_seq = all_codes_flat[i: i + local_w]
            real_tokens = sum(1 for t in window_seq if t != 0)
            if real_tokens < min(MIN_SEQUENCE_TOKENS, local_w):
                continue
            if len(window_seq) < usable_window:
                window_seq = [0] * (usable_window - len(window_seq)) + window_seq
            X.append(window_seq)
            y.append(all_codes_flat[i + local_w])
            session_labels.append("global")

    if not X:
        raise ValueError(
            "No valid sequences found. All sequences had fewer than "
            f"{MIN_SEQUENCE_TOKENS} real log tokens. "
            "Try uploading a larger or more varied log file."
        )

    return np.array(X), np.array(y), session_labels


# ── Statistical Features ──────────────────────

def compute_statistical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds event frequency, entropy, and time-based features."""
    df = df.copy()

    freq = df["template_id"].value_counts(normalize=True)
    df["event_freq"]       = df["template_id"].map(freq)
    df["template_entropy"] = -np.log(df["event_freq"].clip(lower=1e-6))

    if "parsed_timestamp" in df.columns:
        ts = pd.to_datetime(df["parsed_timestamp"], errors="coerce")
        df["hour_of_day"]    = ts.dt.hour.fillna(-1).astype(int)
        df["is_after_hours"] = df["hour_of_day"].apply(
            lambda h: 1 if (h < 8 or h > 18) else 0
        )
    else:
        df["hour_of_day"]    = -1
        df["is_after_hours"] = 0

    return df


# ── Full Feature Engineering Pipeline ─────────

def run_feature_engineering(df: pd.DataFrame) -> tuple:
    """
    Full pipeline: encode → group sessions → build windows → stat features.
    Stat features and session grouping run in parallel for speed.
    Returns: (df_enriched, X, y, session_labels, vocab)
    """
    # Step 1: Encode (must be sequential — needed by both parallel steps)
    df, vocab = encode_template_ids(df)

    # Step 2: Parallel — stat features + session grouping
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_stats    = executor.submit(compute_statistical_features, df)
        future_sessions = executor.submit(group_into_sessions, df)
        df_enriched     = future_stats.result()
        session_seqs    = future_sessions.result()

    # Step 3: Build sliding windows with quality filter
    X, y, session_labels = build_sequences(session_seqs)

    save_processed(df_enriched, "features")
    return df_enriched, X, y, session_labels, vocab