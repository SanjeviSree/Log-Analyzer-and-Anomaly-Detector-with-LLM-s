# models/ensemble.py
# ─────────────────────────────────────────────
# Combines LogBERT + DeepLog scores
# Uses dual threshold (absolute + percentile) to prevent
# normal data being flagged as anomalies
# ─────────────────────────────────────────────

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from models.logbert  import run_logbert_inference
from models.deeplog  import run_deeplog_inference
from utils.constants import (
    LOGBERT_WEIGHT, DEEPLOG_WEIGHT,
    ANOMALY_TYPES, ANOMALY_THRESHOLD, ANOMALY_PERCENTILE,
)
from utils.helpers import map_score_to_severity, rank_anomalies, normalize_scores


# ── Score Fusion ──────────────────────────────

def fuse_scores(logbert_scores: list, deeplog_scores: list) -> list:
    """
    Weighted average: LogBERT (70%) + DeepLog (30%).
    Aligns lengths before fusing.
    """
    lb = np.array(logbert_scores)
    dl = np.array(deeplog_scores)
    n  = min(len(lb), len(dl))
    return (LOGBERT_WEIGHT * lb[:n] + DEEPLOG_WEIGHT * dl[:n]).tolist()


def apply_entropy_boost(fused_scores: list, sequences: list) -> list:
    """
    Boosts anomaly scores for sequences containing rare token patterns.

    Logic: If a sequence contains tokens that appear very infrequently
    across ALL sequences (rare EventIDs / unusual log templates),
    it is more likely to be an attack event.

    This directly addresses missed anomalies where attack logs have
    similar structure to normal logs but contain rare EventIDs like
    4740 (lockout), 4688 (new process), 1116 (malware detected).

    Boost formula:
      final_score = fused_score + (rarity_boost * 0.15)
    Max boost: 0.15 — prevents normal rare events from becoming CRITICAL
    """
    from collections import Counter

    # Count how often each token appears across all sequences
    all_tokens = []
    for seq in sequences:
        all_tokens.extend(seq)
    token_counts = Counter(all_tokens)
    total_tokens = max(len(all_tokens), 1)

    boosted = []
    for i, score in enumerate(fused_scores):
        if i >= len(sequences):
            boosted.append(score)
            continue

        seq = sequences[i]
        if not seq:
            boosted.append(score)
            continue

        # Calculate rarity: average inverse frequency of tokens in sequence
        # Rare tokens (low count) = high rarity score
        rarity_scores = []
        for tok in seq:
            if tok == 0:   # skip padding
                continue
            freq  = token_counts[tok] / total_tokens
            # Tokens appearing in <1% of all logs get high rarity
            rarity = max(0.0, 1.0 - (freq * 100))
            rarity_scores.append(rarity)

        if rarity_scores:
            avg_rarity  = sum(rarity_scores) / len(rarity_scores)
            boost       = avg_rarity * 0.15   # max 0.15 boost
            final_score = min(1.0, score + boost)
        else:
            final_score = score

        boosted.append(final_score)

    return boosted


# ── Dual-Threshold Anomaly Filter ─────────────

def high_confidence_filter(fused_scores: list) -> list:
    """
    Flags a sequence as anomalous ONLY when it passes BOTH conditions:

    Condition 1 — Absolute threshold:
        Score must be >= ANOMALY_THRESHOLD (0.72).
        Prevents low-scoring noise from being flagged.

    Condition 2 — Percentile cutoff:
        Score must be in the top (100 - ANOMALY_PERCENTILE)% of all scores.
        Default: top 15% (85th percentile and above).
        Prevents mass-flagging when all scores cluster high.

    Both conditions must be true → anomaly.
    Either fails → normal.

    This is the PRIMARY fix for "normal data flagged as anomaly".
    The old threshold of 0.50 flagged ~50% of all sequences.
    This approach flags only the genuinely unusual top 15%.
    """
    arr = np.array(fused_scores)

    # Condition 1: absolute floor
    abs_mask = arr >= ANOMALY_THRESHOLD

    # Condition 2: percentile ceiling — top 15% only
    percentile_cut = np.percentile(arr, ANOMALY_PERCENTILE)
    pct_mask       = arr >= percentile_cut

    # Both must be true
    combined = abs_mask & pct_mask
    return combined.tolist()


# ── Anomaly Type Mapping ──────────────────────

def _assign_anomaly_type(template: str) -> str:
    """
    Maps a Drain3 log template to a human-readable anomaly type.
    Uses keyword matching first, then deterministic hash fallback.
    """
    t = template.lower()

    keyword_map = {
        "brute":        "Brute Force Attack",
        "scan":         "Port Scanning",
        "privilege":    "Privilege Escalation",
        "lateral":      "Lateral Movement",
        "exfil":        "Data Exfiltration",
        "malware":      "Malware Activity",
        "unauthorized": "Unauthorized Access",
        "logon":        "Suspicious Login",
        "login":        "Suspicious Login",
        "signin":       "Suspicious Login",
        "ddos":         "DDoS Pattern",
        "flood":        "DDoS Pattern",
        "firewall":     "Firewall Rule Violation",
        "blocked":      "Firewall Rule Violation",
        "outbound":     "Unusual Outbound Traffic",
        "lockout":      "Account Lockout Spike",
        "locked":       "Account Lockout Spike",
        "dump":         "Credential Dumping",
        "mimikatz":     "Credential Dumping",
        "process":      "Abnormal Process Execution",
        "exec":         "Abnormal Process Execution",
        "auth":         "Repeated Auth Failures",
        "fail":         "Repeated Auth Failures",
        "denied":       "Repeated Auth Failures",
        "network":      "Unusual Outbound Traffic",
        "connect":      "Unusual Outbound Traffic",
    }

    for keyword, anomaly_type in keyword_map.items():
        if keyword in t:
            return anomaly_type

    # Deterministic fallback using template hash
    return ANOMALY_TYPES[abs(hash(template)) % len(ANOMALY_TYPES)]


# ── Main Ensemble Pipeline ────────────────────

def run_ensemble(
    X: np.ndarray,
    y: np.ndarray,
    sequences: list,
    df_features: pd.DataFrame,
    session_labels: list,
) -> pd.DataFrame:
    """
    Full ensemble pipeline:
      1. Run LogBERT + DeepLog inference in parallel threads
      2. Fuse scores (weighted average)
      3. Apply dual-threshold filter (absolute + percentile)
      4. Build ranked anomaly DataFrame (top 10 + bottom 10)

    Returns DataFrame with columns:
    [sno, anomaly_name, type, confidence, severity,
     session_id, log_template, raw_log_sample, explanation, solution]
    """
    print("[Ensemble] Running LogBERT + DeepLog in parallel...")
    with ThreadPoolExecutor(max_workers=2) as ex:
        lb_future      = ex.submit(run_logbert_inference, sequences)
        dl_future      = ex.submit(run_deeplog_inference, X, y)
        logbert_scores = lb_future.result()
        deeplog_scores = dl_future.result()

    fused      = fuse_scores(logbert_scores, deeplog_scores)
    fused      = apply_entropy_boost(fused, sequences)  # boost rare token patterns
    is_anomaly = high_confidence_filter(fused)

    total_flagged = sum(1 for f in is_anomaly if f)
    print(f"[Ensemble] {total_flagged} anomalies flagged out of {len(fused)} sequences")
    print(f"[Ensemble] Threshold: abs>={ANOMALY_THRESHOLD}, percentile>={ANOMALY_PERCENTILE}th")

    # ── Build result rows ──────────────────────
    template_col = "log_template" if "log_template" in df_features.columns else None
    rows = []

    for i, (flag, score) in enumerate(zip(is_anomaly, fused)):
        if not flag:
            continue

        template   = ""
        raw_sample = ""

        if template_col and i < len(df_features):
            row_data   = df_features.iloc[i]
            template   = str(row_data.get("log_template", ""))
            # Try multiple columns for the raw log sample
            for col in ["message", "msg", "description", "raw_log", "event_data"]:
                if col in df_features.columns:
                    raw_sample = str(row_data.get(col, ""))[:300]
                    if raw_sample and raw_sample != "nan":
                        break
            if not raw_sample:
                raw_sample = str(row_data.to_dict())[:300]

        severity = map_score_to_severity(score)
        atype    = _assign_anomaly_type(template)

        rows.append({
            "anomaly_name":   atype,
            "type":           atype,
            "confidence":     round(score, 4),
            "severity":       severity,
            "session_id":     session_labels[i] if i < len(session_labels) else f"seq_{i}",
            "log_template":   template,
            "raw_log_sample": raw_sample,
            "explanation":    "",   # filled by llm/ollama_client.py
            "solution":       "",   # filled by llm/ollama_client.py
        })

    if not rows:
        print("[Ensemble] No anomalies passed the dual threshold. Returning empty DataFrame.")
        return pd.DataFrame(columns=[
            "sno", "anomaly_name", "type", "confidence", "severity",
            "session_id", "log_template", "raw_log_sample", "explanation", "solution"
        ])

    result_df = pd.DataFrame(rows)
    result_df = rank_anomalies(result_df)   # top 10 + bottom 10
    result_df.insert(0, "sno", range(1, len(result_df) + 1))

    print(f"[Ensemble] Final output: {len(result_df)} anomalies after ranking")
    return result_df