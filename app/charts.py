# app/charts.py
# ─────────────────────────────────────────────
# Bar chart: Anomaly Name vs Severity Level
# ─────────────────────────────────────────────

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.constants import SEVERITY, SEVERITY_COLOR


def render_anomaly_chart(df: pd.DataFrame):
    if df.empty:
        return

    chart_df = df[["anomaly_name", "severity", "confidence"]].copy()
    chart_df["severity_score"] = chart_df["severity"].map(SEVERITY).fillna(1)
    chart_df["color"]          = chart_df["severity"].map(SEVERITY_COLOR).fillna("#B0BEC5")
    chart_df = chart_df.sort_values("severity_score", ascending=True)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=chart_df["severity_score"],
        y=chart_df["anomaly_name"],
        orientation="h",
        marker=dict(
            color=chart_df["color"],
            line=dict(color="rgba(0,0,0,0.15)", width=0.5),
        ),
        text=chart_df.apply(
            lambda r: f"{r['severity']}  ({r['confidence']:.0%})", axis=1
        ),
        textposition="outside",
        textfont=dict(size=12, color="#94a3b8"),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Severity: %{text}<br>"
            "Confidence: %{customdata:.0%}<extra></extra>"
        ),
        customdata=chart_df["confidence"],
    ))

    fig.update_layout(
        xaxis=dict(
            title=dict(
                text="Severity Level",
                font=dict(size=13, color="#94a3b8"),
            ),
            tickvals=[1, 2, 3, 4, 5],
            ticktext=["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
            tickfont=dict(size=11, color="#64748b"),
            range=[0, 6.5],
            showgrid=True,
            gridcolor="rgba(59,130,246,0.08)",
            zeroline=False,
        ),
        yaxis=dict(
            title=dict(
                text="Anomaly Type",
                font=dict(size=13, color="#94a3b8"),
            ),
            tickfont=dict(size=12, color="#cbd5e1"),
            automargin=True,          # prevents y-axis labels getting clipped
        ),
        margin=dict(l=10, r=150, t=30, b=60),
        height=min(500, max(300, len(chart_df) * 35)),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12, color="#94a3b8"),
        showlegend=False,
        bargap=0.35,
    )

    st.plotly_chart(fig, use_container_width=True)