# pipeline/validator.py
# ─────────────────────────────────────────────
# Validates uploaded file formats before parsing
# ─────────────────────────────────────────────

import os
import streamlit as st
from utils.constants import SUPPORTED_FORMATS, FORMAT_ERROR_MSG
from utils.helpers import get_file_extension


def validate_uploaded_file(uploaded_file) -> bool:
    """
    Checks if a Streamlit UploadedFile has a supported extension.
    Shows an error message in the UI if not.
    Returns True if valid, False otherwise.
    """
    if uploaded_file is None:
        st.warning("⚠️ No file uploaded yet.")
        return False

    ext = get_file_extension(uploaded_file.name)

    if ext not in SUPPORTED_FORMATS:
        st.error(FORMAT_ERROR_MSG)
        st.info(
            f"**Supported formats:** "
            + ", ".join(f"`{f}`" for f in SUPPORTED_FORMATS)
        )
        return False

    return True


def validate_file_path(filepath: str) -> bool:
    """
    Validates a file path from C:/Logs exists and is readable.
    Returns True if valid, False otherwise.
    """
    if not os.path.exists(filepath):
        st.error(f"❌ File not found: `{filepath}`")
        return False

    if not os.path.isfile(filepath):
        st.error(f"❌ Path is not a file: `{filepath}`")
        return False

    ext = get_file_extension(filepath)
    if ext not in SUPPORTED_FORMATS:
        st.error(FORMAT_ERROR_MSG)
        return False

    return True


def validate_dataframe(df) -> tuple[bool, str]:
    """
    Basic sanity checks on a parsed DataFrame.
    Returns (is_valid: bool, message: str)
    """
    import pandas as pd

    if df is None:
        return False, "DataFrame is None — parsing may have failed."

    if not isinstance(df, pd.DataFrame):
        return False, "Expected a pandas DataFrame."

    if df.empty:
        return False, "The file is empty or has no parseable rows."

    if len(df.columns) < 2:
        return False, "File has too few columns to analyze."

    return True, f"✅ Loaded {len(df):,} rows × {len(df.columns)} columns."