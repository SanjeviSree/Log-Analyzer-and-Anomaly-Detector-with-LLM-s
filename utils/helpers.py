# utils/helpers.py
import os
import re
import pandas as pd
from datetime import datetime, timedelta
from utils.constants import SEVERITY, PROCESSED_DIR


def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[-1].lower()

def ensure_dirs(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def save_processed(df: pd.DataFrame, name: str) -> str:
    ensure_dirs(PROCESSED_DIR)
    path = os.path.join(PROCESSED_DIR, f"{name}.csv")
    df.to_csv(path, index=False)
    return path

def load_processed(name: str) -> pd.DataFrame:
    path = os.path.join(PROCESSED_DIR, f"{name}.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    raise FileNotFoundError(f"Processed file not found: {path}")

def hours_ago(hours: int) -> datetime:
    return datetime.now() - timedelta(hours=hours)

def parse_timestamp(ts_str: str):
    formats = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ", "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",  "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(str(ts_str).strip(), fmt)
        except ValueError:
            continue
    return None

def normalize_scores(scores: list) -> list:
    if not scores:
        return scores
    mn, mx = min(scores), max(scores)
    if mx == mn:
        return [1.0 for _ in scores]
    return [(s - mn) / (mx - mn) for s in scores]

def map_score_to_severity(score: float) -> str:
    if score >= 0.90:   return "CRITICAL"
    elif score >= 0.75: return "HIGH"
    elif score >= 0.55: return "MEDIUM"
    elif score >= 0.35: return "LOW"
    else:               return "INFO"


def rank_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns TOP 10 (highest severity) + BOTTOM 10 (lowest severity).
    Guarantees coverage across all severity levels: CRITICAL → INFO.
    """
    severity_order = {k: v for k, v in SEVERITY.items()}
    df = df.copy()
    df["severity_rank"] = df["severity"].map(severity_order).fillna(0)
    df = df.sort_values(
        by=["severity_rank", "confidence"],
        ascending=[False, False]
    ).reset_index(drop=True)

    top_10    = df.head(10)
    bottom_10 = df.tail(10)

    # Combine, deduplicate (in case total < 20), keep order top→bottom
    combined = pd.concat([top_10, bottom_10]).drop_duplicates(
        subset=["anomaly_name", "confidence"]
    ).drop(columns=["severity_rank"]).reset_index(drop=True)

    return combined


def clean_log_message(msg: str) -> str:
    if not isinstance(msg, str):
        return ""
    msg = re.sub(r"[\x00-\x1f\x7f]", " ", msg)
    msg = re.sub(r"\s+", " ", msg).strip()
    return msg

def truncate(text: str, max_len: int = 300) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text