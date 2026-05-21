# app/main.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from app.style         import inject_styles, render_header, render_section_badge, render_empty_state
from app.results_table import render_anomaly_table
from app.charts        import render_anomaly_chart

st.set_page_config(
    page_title="Log Analyzer and Anomaly Detector with LLM's",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject full UI theme ──────────────────────
inject_styles()
render_header()
st.divider()

# ── Input Tabs ────────────────────────────────
tab1, tab2 = st.tabs(["📂  Manual Upload", "📡  Live Log Collection"])

df_feat, X, y, session_labels, vocab = None, None, None, None, None

with tab1:
    from app.upload_logs import render_upload_section
    result = render_upload_section()
    if result[0] is not None:
        df_feat, X, y, session_labels, vocab = result

with tab2:
    if df_feat is None:
        from app.live_logs import render_live_section
        result = render_live_section()
        if result[0] is not None:
            df_feat, X, y, session_labels, vocab = result

# ── Analysis ──────────────────────────────────
if df_feat is not None and X is not None:
    st.divider()
    render_section_badge("🔬", "Anomaly Detection")

    with st.spinner("🤖 Running LogBERT + DeepLog ensemble..."):
        from utils.constants import DEEPLOG_MODEL, LOGBERT_MODEL
        missing = []
        if not os.path.exists(DEEPLOG_MODEL):
            missing.append("DeepLog")
        if not os.path.exists(os.path.join(LOGBERT_MODEL, "logbert.pt")):
            missing.append("LogBERT")

        if missing:
            st.warning(f"⚠️ Models not trained yet: {', '.join(missing)}")
            st.info(
                "**Run this once to train:**\n"
                "```bash\ncd C:\\log_anomaly_detector\npython train_models.py\n```\n"
                "Takes ~8–12 minutes. After training, re-run the analysis."
            )
            if st.button("🚀 Train Models Now", type="primary"):
                with st.spinner("Training in progress... (~8–12 mins, keep this tab open)"):
                    try:
                        import subprocess
                        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        proc = subprocess.run(
                            [sys.executable, "train_models.py"],
                            capture_output=True, text=True, cwd=root
                        )
                        if proc.returncode == 0:
                            st.success("✅ Training complete! Re-run your analysis.")
                            st.code(proc.stdout[-3000:])
                        else:
                            st.error("❌ Training failed:")
                            st.code(proc.stderr[-3000:])
                    except Exception as e:
                        st.error(f"❌ {e}")
            st.stop()

        seq_list = [row.tolist() for row in X]
        try:
            from models.ensemble import run_ensemble
            anomaly_df = run_ensemble(X, y, seq_list, df_feat, session_labels)
        except Exception as e:
            st.error(f"❌ Ensemble error: {e}")
            st.stop()

    if anomaly_df.empty:
        st.success("✅ No significant anomalies detected above confidence threshold.")
    else:
        # ── LLM ──────────────────────────────
        st.divider()
        render_section_badge("🧠", "LLAMA3 Analysis")
        from llm.ollama_client import run_llm_pipeline
        summary, anomaly_df = run_llm_pipeline(anomaly_df, log_type="Windows")

        # ── Summary ───────────────────────────
        st.divider()
        render_section_badge("📋", "Executive Summary")
        st.markdown(f"""
        <div style="background:rgba(15,22,41,0.8); border:1px solid rgba(59,130,246,0.25);
                    border-left:3px solid #3b82f6; border-radius:12px;
                    padding:1.25rem 1.5rem; margin:0.5rem 0 1rem;">
            <p style="color:#cbd5e1; font-size:0.95rem; line-height:1.8;
                      margin:0; text-align:justify;">{summary}</p>
        </div>
        """, unsafe_allow_html=True)

        # ── Table ─────────────────────────────
        st.divider()
        render_section_badge("🚨", f"Top 10 + Bottom 10 Anomalies  ({len(anomaly_df)} total)")
        render_anomaly_table(anomaly_df)

        # ── Chart ─────────────────────────────
        st.divider()
        render_section_badge("📊", "Severity Overview")
        render_anomaly_chart(anomaly_df)

else:
    render_empty_state()