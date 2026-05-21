# app/upload_logs.py
# ─────────────────────────────────────────────
# Manual file upload input section
# ─────────────────────────────────────────────

import streamlit as st
import pandas as pd
from pipeline.validator import validate_uploaded_file, validate_dataframe
from pipeline.parser    import parse_uploaded_file
from pipeline.cleaner   import run_cleaning_pipeline
from pipeline.features  import run_feature_engineering


def render_upload_section() -> tuple[pd.DataFrame | None, any, any, any, any]:
    """
    Renders the manual upload UI.
    Returns (df_features, X, y, session_labels, vocab) or (None, ...) if no file.
    """
    st.header("📂 Manual Log Upload")
    st.caption("Supported formats: JSON, CSV, XML, TXT, LOG, SYSLOG")

    uploaded = st.file_uploader(
        label="Drop your log file here",
        type=["json", "csv", "xml", "txt", "log", "syslog"],
        help="Files from C:/Logs or any exported Windows log",
    )

    if uploaded is None:
        return None, None, None, None, None

    # Validate format
    if not validate_uploaded_file(uploaded):
        return None, None, None, None, None

    with st.spinner("📥 Parsing file..."):
        try:
            raw_df = parse_uploaded_file(uploaded)
        except Exception as e:
            st.error(f"❌ Failed to parse file: {e}")
            return None, None, None, None, None

    valid, msg = validate_dataframe(raw_df)
    if not valid:
        st.error(msg)
        return None, None, None, None, None

    st.success(msg)

    with st.spinner("🧹 Cleaning and parsing log templates..."):
        cleaned_df = run_cleaning_pipeline(raw_df, save_name="upload_cleaned")

    with st.spinner("⚙️ Engineering features..."):
        try:
            df_feat, X, y, session_labels, vocab = run_feature_engineering(cleaned_df)
        except ValueError as e:
            st.warning(f"⚠️ {e}")
            return None, None, None, None, None

    st.success(f"✅ Ready — {len(X)} sequences prepared for model inference.")
    return df_feat, X, y, session_labels, vocab