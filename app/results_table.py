# app/results_table.py
import streamlit as st
import pandas as pd

# Severity color map — text color + background
SEVERITY_STYLE = {
    "CRITICAL": {"color": "#FF4C4C", "bg": "rgba(255,76,76,0.15)",  "border": "#FF4C4C"},
    "HIGH":     {"color": "#FF8C00", "bg": "rgba(255,140,0,0.15)",  "border": "#FF8C00"},
    "MEDIUM":   {"color": "#FFD700", "bg": "rgba(255,215,0,0.15)",  "border": "#FFD700"},
    "LOW":      {"color": "#4FC3F7", "bg": "rgba(79,195,247,0.15)", "border": "#4FC3F7"},
    "INFO":     {"color": "#94A3B8", "bg": "rgba(148,163,184,0.12)","border": "#94A3B8"},
}

ALL_COLUMNS = {
    "sno":          "#",
    "anomaly_name": "Anomaly Name",
    "type":         "Type",
    "confidence":   "Confidence",
    "severity":     "Severity",
    "explanation":  "Explanation",
    "solution":     "Solution",
    "session_id":   "Session ID",
    "log_template": "Log Template",
}

DEFAULT_COLUMNS = ["sno", "anomaly_name", "type", "confidence",
                   "severity", "explanation", "solution"]


def _sev_badge_html(severity: str) -> str:
    """Returns an HTML severity badge string."""
    s    = str(severity).upper()
    info = SEVERITY_STYLE.get(s, SEVERITY_STYLE["INFO"])
    return (
        f'<span style="'
        f'background:{info["bg"]};'
        f'color:{info["color"]};'
        f'border:1px solid {info["border"]};'
        f'font-weight:700;'
        f'font-size:0.75rem;'
        f'padding:3px 10px;'
        f'border-radius:20px;'
        f'letter-spacing:0.5px;'
        f'white-space:nowrap;'
        f'">{s}</span>'
    )


def render_anomaly_table(df: pd.DataFrame):
    if df.empty:
        st.info("✅ No anomalies detected above confidence threshold.")
        return

    # ── Column selector ──────────────────────────
    available = [c for c in ALL_COLUMNS if c in df.columns]
    default   = [c for c in DEFAULT_COLUMNS if c in df.columns]

    with st.expander("⚙️ Customize Columns", expanded=False):
        selected_keys = st.multiselect(
            label="Select columns to display:",
            options=available,
            default=default,
            format_func=lambda x: ALL_COLUMNS.get(x, x),
            key="col_selector"
        )

    if not selected_keys:
        selected_keys = default

    # ── Build HTML table ──────────────────────────
    # Use HTML rendering so severity gets real color badges
    # All other columns render as plain text

    header_cols = [ALL_COLUMNS.get(c, c) for c in selected_keys]

    # Column width hints (approximate %)
    col_widths = {
        "#":           "3%",
        "Anomaly Name":"13%",
        "Type":        "13%",
        "Confidence":  "7%",
        "Severity":    "8%",
        "Explanation": "28%",
        "Solution":    "28%",
        "Session ID":  "8%",
        "Log Template":"20%",
    }

    # Build header row
    header_html = "".join(
        f'<th style="background:#0F1629; color:#3B82F6; font-size:0.72rem;'
        f'font-weight:700; text-transform:uppercase; letter-spacing:0.8px;'
        f'padding:10px 12px; border-bottom:1px solid rgba(59,130,246,0.3);'
        f'width:{col_widths.get(h,"auto")}; white-space:nowrap;">{h}</th>'
        for h in header_cols
    )

    # Build data rows
    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        row_bg = "rgba(15,22,41,0.8)" if i % 2 == 0 else "rgba(20,29,53,0.8)"
        cells  = ""

        for key in selected_keys:
            val = row.get(key, "")

            if key == "severity":
                cell_content = _sev_badge_html(str(val))
                align = "center"
            elif key == "confidence":
                try:
                    pct = f"{float(val):.0%}"
                except Exception:
                    pct = str(val)
                sev  = str(row.get("severity", "INFO")).upper()
                info = SEVERITY_STYLE.get(sev, SEVERITY_STYLE["INFO"])
                cell_content = (
                    f'<span style="color:{info["color"]};'
                    f'font-weight:600;">{pct}</span>'
                )
                align = "center"
            elif key == "sno":
                cell_content = (
                    f'<span style="color:#64748B; font-weight:600;">{val}</span>'
                )
                align = "center"
            elif key == "anomaly_name":
                cell_content = (
                    f'<span style="color:#F0F4FF; font-weight:600;">{val}</span>'
                )
                align = "left"
            elif key in ("explanation", "solution"):
                cell_content = (
                    f'<span style="color:#CBD5E1; font-size:0.82rem;'
                    f'line-height:1.5;">{str(val)}</span>'
                )
                align = "left"
            else:
                cell_content = (
                    f'<span style="color:#94A3B8; font-size:0.82rem;">{val}</span>'
                )
                align = "left"

            cells += (
                f'<td style="background:{row_bg}; padding:10px 12px;'
                f'border-bottom:1px solid rgba(30,58,95,0.5);'
                f'text-align:{align}; vertical-align:top;">'
                f'{cell_content}</td>'
            )

        rows_html += f"<tr>{cells}</tr>"

    table_html = f"""
    <div style="overflow-x:auto; border:1px solid rgba(59,130,246,0.2);
                border-radius:12px; margin-bottom:1rem;">
      <table style="width:100%; border-collapse:collapse;
                    font-family:'Inter',sans-serif; font-size:0.85rem;">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """

    st.markdown(table_html, unsafe_allow_html=True)

    # ── Download button ───────────────────────────
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Full Report (CSV)",
        data=csv,
        file_name="anomaly_report.csv",
        mime="text/csv",
    )