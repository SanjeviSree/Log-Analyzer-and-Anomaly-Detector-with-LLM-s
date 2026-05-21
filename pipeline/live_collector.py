# pipeline/live_collector.py
# ─────────────────────────────────────────────
# Pulls live logs from Windows Event Log
# Uses: win32evtlog (pywin32)
# ─────────────────────────────────────────────

import pandas as pd
from datetime import datetime
from utils.constants import LOG_FILES, LOG_SOURCE_DIR, TIME_RANGES
from utils.helpers import hours_ago

try:
    import win32evtlog
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


# ── Windows Event Log Channel Map ────────────
CHANNEL_MAP = {
    "Security": "Security",
    "Network":  "System",       # Network events live in System log on Windows
    "Firewall": "Security",     # Firewall events are under Security channel
}

# ── Firewall Event IDs ────────────────────────
FIREWALL_EVENT_IDS = {2004, 2005, 2006, 2033, 4950, 4951, 4952, 4953}


# ── Main Collector ────────────────────────────

def collect_live_logs(log_types: list[str], time_range_label: str) -> pd.DataFrame:
    """
    Collects Windows logs for given log types and time range.
    Falls back to reading from C:/Logs CSV files if pywin32 is unavailable.

    Args:
        log_types       : List of selected types e.g. ["Security", "Network"]
        time_range_label: One of TIME_RANGES keys e.g. "Past 1 Hour"

    Returns:
        Combined DataFrame of all requested log types
    """
    hours = TIME_RANGES.get(time_range_label, 24)
    since = hours_ago(hours)

    if WIN32_AVAILABLE:
        return _collect_from_event_log(log_types, since)
    else:
        return _collect_from_csv_fallback(log_types, since)


# ── Windows Event Log Reader ──────────────────

def _collect_from_event_log(log_types: list[str], since: datetime) -> pd.DataFrame:
    """Reads directly from Windows Event Log using pywin32."""
    all_rows = []

    for log_type in log_types:
        channel = CHANNEL_MAP.get(log_type, "System")
        rows = _read_channel(channel, since, log_type)
        all_rows.extend(rows)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Only sort if time_generated column exists and has values
    if "time_generated" in df.columns:
        df["time_generated"] = df["time_generated"].fillna("")
        df.sort_values("time_generated", ascending=False, inplace=True)

    df.reset_index(drop=True, inplace=True)
    return df


def _read_channel(channel: str, since: datetime, log_type: str) -> list[dict]:
    """Reads events from a specific Windows Event Log channel."""
    rows = []

    try:
        hand = win32evtlog.OpenEventLog(None, channel)
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

        while True:
            events = win32evtlog.ReadEventLog(hand, flags, 0)
            if not events:
                break

            for event in events:
                event_time = event.TimeGenerated

                # Convert to naive datetime for comparison
                event_dt = datetime(
                    event_time.year, event_time.month, event_time.day,
                    event_time.hour, event_time.minute, event_time.second
                )

                if event_dt < since:
                    break  # Older than our range — stop

                # Filter firewall events by Event ID
                if log_type == "Firewall" and event.EventID not in FIREWALL_EVENT_IDS:
                    continue

                row = {
                    "log_type":       log_type,
                    "event_id":       event.EventID,
                    "event_category": event.EventCategory,
                    "event_type":     _type_label(event.EventType),
                    "source_name":    event.SourceName,
                    "computer_name":  event.ComputerName,
                    "time_generated": event_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "message":        " | ".join(event.StringInserts or []),
                }
                rows.append(row)

        win32evtlog.CloseEventLog(hand)

    except Exception as e:
        rows.append({
            "log_type": log_type,
            "message":  f"[ERROR reading {channel}]: {str(e)}",
            "event_id": -1,
        })

    return rows


def _type_label(event_type: int) -> str:
    return {
        win32con.EVENTLOG_ERROR_TYPE:       "ERROR",
        win32con.EVENTLOG_WARNING_TYPE:     "WARNING",
        win32con.EVENTLOG_INFORMATION_TYPE: "INFORMATION",
        win32con.EVENTLOG_AUDIT_SUCCESS:    "AUDIT_SUCCESS",
        win32con.EVENTLOG_AUDIT_FAILURE:    "AUDIT_FAILURE",
    }.get(event_type, "UNKNOWN") if WIN32_AVAILABLE else "UNKNOWN"


# ── CSV Fallback (for dev / non-Windows) ──────

def _collect_from_csv_fallback(log_types: list[str], since: datetime) -> pd.DataFrame:
    """
    Reads from C:/Logs CSV files when pywin32 is not available.
    Filters rows by parsed timestamp where possible.
    """
    import os

    dfs = []
    for log_type in log_types:
        files = LOG_FILES.get(log_type, [])
        for fname in files:
            fpath = os.path.join(LOG_SOURCE_DIR, fname)
            if not os.path.exists(fpath):
                continue
            try:
                df = pd.read_csv(fpath, low_memory=False)
                df["log_type"] = log_type

                # Try to filter by timestamp
                ts_cols = [c for c in df.columns if any(
                    k in c.lower() for k in ["time", "date", "timestamp"]
                )]
                if ts_cols:
                    df[ts_cols[0]] = pd.to_datetime(df[ts_cols[0]], errors="coerce")
                    df = df[df[ts_cols[0]] >= since]

                dfs.append(df)
            except Exception:
                continue

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    return combined