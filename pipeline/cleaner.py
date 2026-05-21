# pipeline/cleaner.py
# ─────────────────────────────────────────────
# Step 1: Pandas-based cleaning
# Step 2: Drain3 log template extraction
# ─────────────────────────────────────────────

import re
import hashlib
import pandas as pd
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from utils.helpers import parse_timestamp, save_processed


# ── Drain3 Setup ──────────────────────────────

def _build_drain3() -> TemplateMiner:
    """
    Creates a Drain3 TemplateMiner compatible with drain3 >= 0.9.
    load_defaults() was removed in newer versions — set attrs directly.
    """
    config = TemplateMinerConfig()

    # Core drain params (set directly — no load_defaults() in newer drain3)
    config.drain_sim_th       = 0.3   # lowered: more distinct templates per log type
    config.drain_depth        = 6     # deeper tree: better log differentiation
    config.drain_max_children = 200   # more children: handles wider log variety

    # Disable persistence (no .bin file saved to disk)
    config.snapshot_interval_minutes = 0
    config.compress_state             = False

    # Disable profiling safely
    try:
        config.profiling_enabled = False
    except AttributeError:
        pass

    return TemplateMiner(config=config)


# ── Cleaning ──────────────────────────────────

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full Pandas cleaning pipeline:
    1. Drop duplicates
    2. Drop columns that are >80% null
    3. Fill remaining nulls
    4. Parse timestamps
    5. Normalize text fields
    """
    df = df.copy()

    # 1. Drop duplicates
    df.drop_duplicates(inplace=True)

    # 2. Drop columns with >80% nulls
    threshold = 0.8 * len(df)
    df = df.loc[:, df.isnull().sum() < threshold]

    # 3. Fill nulls
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("unknown")
    for col in df.select_dtypes(include="number").columns:
        df[col] = df[col].fillna(0)

    # 4. Parse timestamps — look for common timestamp column names
    ts_candidates = [c for c in df.columns if any(
        k in c for k in ["time", "date", "timestamp", "ts", "created"]
    )]
    if ts_candidates:
        col = ts_candidates[0]
        df["parsed_timestamp"] = df[col].apply(
            lambda x: parse_timestamp(str(x))
        )

    # 5. Normalize known severity/level columns
    level_cols = [c for c in df.columns if any(
        k in c for k in ["level", "severity", "priority", "eventtype"]
    )]
    for col in level_cols:
        df[col] = df[col].astype(str).str.upper().str.strip()

    df.reset_index(drop=True, inplace=True)
    return df


# ── Log Message Extraction ────────────────────

def extract_log_messages(df: pd.DataFrame) -> list[str]:
    """
    Extracts log messages enriched with EventID/Level prefix.
    This is the key fix for missing anomalies:
    By prefixing EventID, logs with same message but different
    EventID get different Drain3 templates.

    Example:
      Before: "An account <*> log on" (same for 4624 and 4625)
      After:  "EVT4624 An account logged on" vs "EVT4625 An account failed"
              → Different templates → Different token IDs → Model can distinguish
    """
    # Find EventID column
    eventid_col = None
    for col in df.columns:
        if any(k in col.lower() for k in ["eventid", "event_id", "evtid"]):
            eventid_col = col
            break

    # Find Level/severity column
    level_col = None
    for col in df.columns:
        if any(k in col.lower() for k in ["level", "severity", "type"]):
            level_col = col
            break

    # Find message column
    priority_cols = ["message", "msg", "description", "event_data",
                     "raw_log", "log_message", "details"]
    msg_col = None
    for col in priority_cols:
        if col in df.columns:
            msg_col = col
            break

    if msg_col is None:
        str_cols = df.select_dtypes(include="object").columns.tolist()
        messages = df[str_cols].apply(
            lambda row: " | ".join(row.astype(str)), axis=1
        ).tolist()
    else:
        messages = df[msg_col].astype(str).tolist()

    # Enrich each message with EventID + Level prefix
    enriched = []
    for i, msg in enumerate(messages):
        prefix_parts = []

        if eventid_col and eventid_col in df.columns:
            eid = str(df.iloc[i].get(eventid_col, "")).strip()
            if eid and eid not in ("nan", "0", ""):
                prefix_parts.append(f"EVT{eid}")

        if level_col and level_col in df.columns:
            lvl = str(df.iloc[i].get(level_col, "")).strip().upper()
            if lvl and lvl not in ("NAN", ""):
                # Shorten level labels for cleaner templates
                lvl_map = {
                    "FAILURE AUDIT": "FAIL",
                    "AUDIT FAILURE": "FAIL",
                    "AUDIT SUCCESS": "SUCCESS",
                    "INFORMATION":   "INFO",
                    "WARNING":       "WARN",
                    "ERROR":         "ERR",
                }
                lvl = lvl_map.get(lvl, lvl[:6])
                prefix_parts.append(lvl)

        prefix = " ".join(prefix_parts)
        enriched.append(f"{prefix} {msg}".strip() if prefix else msg)

    return enriched


# ── Drain3 Parsing ────────────────────────────

def apply_drain3(df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs Drain3 on log messages.
    Adds two new columns to the DataFrame:
      - template_id  : short hash of the extracted template
      - log_template : the Drain3 template string (e.g. "User <*> logged in from <*>")

    Supports both old drain3 (dict return) and new drain3 (object return).
    """
    miner = _build_drain3()
    messages = extract_log_messages(df)

    template_ids  = []
    log_templates = []

    for msg in messages:
        msg_clean = _preprocess_for_drain(msg)
        template  = msg_clean  # safe fallback

        try:
            result = miner.add_log_message(msg_clean)

            if result is not None:
                # ── New drain3: result is an object with .cluster attribute ──
                if hasattr(result, "cluster") and result.cluster is not None:
                    template = result.cluster.get_template()

                # ── Old drain3: result is a dict with "cluster" key ──
                elif isinstance(result, dict) and result.get("cluster") is not None:
                    template = result["cluster"].get_template()

                # ── Fallback: result itself might be the cluster ──
                elif hasattr(result, "get_template"):
                    template = result.get_template()

        except Exception:
            # If drain3 fails on any message, keep raw message as template
            template = msg_clean

        tid = _short_hash(template)
        template_ids.append(tid)
        log_templates.append(template)

    df = df.copy()
    df["template_id"]  = template_ids
    df["log_template"] = log_templates
    return df


def _preprocess_for_drain(msg: str) -> str:
    """Removes IPs, numbers, UUIDs before feeding to Drain3 for better grouping."""
    msg = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}\b", "<IP>", msg)           # IP addresses
    msg = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                 "<UUID>", msg, flags=re.IGNORECASE)                     # UUIDs
    msg = re.sub(r"\b\d{4,}\b", "<NUM>", msg)                           # long numbers
    msg = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", msg)                      # hex values
    return msg


def _short_hash(text: str) -> str:
    """Returns first 8 chars of MD5 hash — used as template_id."""
    return hashlib.md5(text.encode()).hexdigest()[:8]


# ── Full Pipeline ─────────────────────────────

def run_cleaning_pipeline(df: pd.DataFrame, save_name: str = "cleaned") -> pd.DataFrame:
    """
    Convenience function: clean → drain3 → save → return.
    Call this from the Streamlit app.
    """
    df = clean_dataframe(df)
    df = apply_drain3(df)
    save_processed(df, save_name)
    return df