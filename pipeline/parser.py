# pipeline/parser.py
# ─────────────────────────────────────────────
# Reads all supported file formats into a pandas DataFrame
# Handles: CSV, JSON, XML, TXT, LOG, SYSLOG
# ─────────────────────────────────────────────

import io
import json
import pandas as pd
import xml.etree.ElementTree as ET
from utils.helpers import get_file_extension, clean_log_message


# ── Main Entry Point ──────────────────────────

def parse_uploaded_file(uploaded_file) -> pd.DataFrame:
    """
    Accepts a Streamlit UploadedFile object.
    Returns a pandas DataFrame regardless of format.
    """
    ext = get_file_extension(uploaded_file.name)
    raw_bytes = uploaded_file.read()

    parsers = {
        ".csv":    _parse_csv,
        ".json":   _parse_json,
        ".xml":    _parse_xml,
        ".txt":    _parse_text,
        ".log":    _parse_text,
        ".syslog": _parse_syslog,
    }

    parser_fn = parsers.get(ext)
    if parser_fn is None:
        raise ValueError(f"Unsupported format: {ext}")

    df = parser_fn(raw_bytes)
    return _post_process(df)


def parse_file_path(filepath: str) -> pd.DataFrame:
    """
    Accepts a full file path (e.g. from C:/Logs).
    Returns a pandas DataFrame.
    """
    ext = get_file_extension(filepath)

    with open(filepath, "rb") as f:
        raw_bytes = f.read()

    # Reuse the same byte-level parsers
    uploaded_mock = type("F", (), {"name": filepath, "read": lambda self: raw_bytes})()
    return parse_uploaded_file(uploaded_mock)


# ── Format Parsers ────────────────────────────

def _parse_csv(raw_bytes: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(raw_bytes), low_memory=False)
    except Exception:
        # Try with different encoding
        return pd.read_csv(io.BytesIO(raw_bytes), encoding="latin-1", low_memory=False)


def _parse_json(raw_bytes: bytes) -> pd.DataFrame:
    text = raw_bytes.decode("utf-8", errors="replace")
    data = json.loads(text)

    if isinstance(data, list):
        return pd.DataFrame(data)
    elif isinstance(data, dict):
        # Try to find the list inside the dict
        for val in data.values():
            if isinstance(val, list):
                return pd.DataFrame(val)
        return pd.DataFrame([data])
    else:
        raise ValueError("JSON structure not recognized.")


def _parse_xml(raw_bytes: bytes) -> pd.DataFrame:
    root = ET.fromstring(raw_bytes.decode("utf-8", errors="replace"))
    rows = []
    for child in root:
        row = {}
        for elem in child:
            row[elem.tag] = elem.text
        if row:
            rows.append(row)
    if not rows:
        raise ValueError("No parseable records found in XML.")
    return pd.DataFrame(rows)


def _parse_text(raw_bytes: bytes) -> pd.DataFrame:
    """
    Parses plain .txt or .log files.
    Each line becomes a row. Tries to split by common delimiters.
    """
    text = raw_bytes.decode("utf-8", errors="replace")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    if not lines:
        raise ValueError("File is empty.")

    # Detect delimiter from first line
    first = lines[0]
    if "\t" in first:
        delim = "\t"
    elif "|" in first:
        delim = "|"
    elif "," in first:
        delim = ","
    else:
        # No delimiter — treat each line as a raw log message
        return pd.DataFrame({"raw_log": lines})

    # Has a header row
    header = [h.strip() for h in lines[0].split(delim)]
    data_rows = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(delim)]
        if len(parts) == len(header):
            data_rows.append(dict(zip(header, parts)))

    if data_rows:
        return pd.DataFrame(data_rows)
    return pd.DataFrame({"raw_log": lines})


def _parse_syslog(raw_bytes: bytes) -> pd.DataFrame:
    """
    Parses syslog format:
    e.g. Mar 29 10:22:01 hostname process[pid]: message
    """
    import re
    text = raw_bytes.decode("utf-8", errors="replace")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    pattern = re.compile(
        r"^(?P<timestamp>\w{3}\s+\d+\s+[\d:]+)\s+"
        r"(?P<host>\S+)\s+"
        r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?:\s+"
        r"(?P<message>.+)$"
    )

    rows = []
    for line in lines:
        m = pattern.match(line)
        if m:
            rows.append(m.groupdict())
        else:
            rows.append({"raw_log": line})

    return pd.DataFrame(rows)


# ── Post Processing ───────────────────────────

def _post_process(df: pd.DataFrame) -> pd.DataFrame:
    """
    Common cleanup applied to all parsed DataFrames:
    - Normalize column names
    - Clean string values
    - Drop fully empty rows
    """
    # Normalize column names
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]

    # Clean string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(clean_log_message)

    # Drop fully empty rows
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df