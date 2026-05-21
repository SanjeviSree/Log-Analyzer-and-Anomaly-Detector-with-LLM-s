# app/live_logs.py
# ─────────────────────────────────────────────
# Live log collection input section
# ─────────────────────────────────────────────

import streamlit as st
import pandas as pd
from pipeline.live_collector import collect_live_logs
from pipeline.cleaner        import run_cleaning_pipeline
from pipeline.features       import run_feature_engineering
from utils.constants         import LOG_TYPES, TIME_RANGES


def render_live_section() -> tuple[pd.DataFrame | None, any, any, any, any]:
    """
    Renders the live log collection UI.
    Returns (df_features, X, y, session_labels, vocab) or (None, ...) if not triggered.
    """
    st.header("📡 Live Log Collection")
    st.caption("Reads directly from Windows Event Log on this machine")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Select Log Types**")
        selected_types = []
        for lt in LOG_TYPES:
            if st.checkbox(lt, value=(lt == "Security")):
                selected_types.append(lt)

    with col2:
        st.markdown("**Select Time Range**")
        time_range = st.radio(
            label="",
            options=list(TIME_RANGES.keys()),
            index=0,
        )

    if not selected_types:
        st.warning("⚠️ Please select at least one log type.")
        return None, None, None, None, None

    collect_btn = st.button("🔄 Collect Logs Now", type="primary")

    if not collect_btn:
        return None, None, None, None, None

    with st.spinner(f"📡 Collecting {', '.join(selected_types)} logs for {time_range}..."):
        try:
            raw_df = collect_live_logs(selected_types, time_range)
        except Exception as e:
            st.error(f"❌ Collection failed: {e}")
            return None, None, None, None, None

    if raw_df.empty:
        st.warning("⚠️ No logs found for the selected type and time range.")
        return None, None, None, None, None

    st.success(f"✅ Collected {len(raw_df):,} log entries.")

    log_type_label = " + ".join(selected_types)

    with st.spinner("🧹 Cleaning logs..."):
        cleaned_df = run_cleaning_pipeline(raw_df, save_name="live_cleaned")

    with st.spinner("⚙️ Engineering features..."):
        try:
            df_feat, X, y, session_labels, vocab = run_feature_engineering(cleaned_df)
        except ValueError as e:
            st.warning(f"⚠️ {e}")
            return None, None, None, None, None

    st.success(f"✅ Ready — {len(X)} sequences prepared for model inference.")
    return df_feat, X, y, session_labels, vocab