# app/style.py
# ─────────────────────────────────────────────
# Full UI/UX styling for the Streamlit app
# Inject with: inject_styles() in main.py
# ─────────────────────────────────────────────

import streamlit as st

def inject_styles():
    st.markdown("""
    <style>

    /* ── Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ── Root Variables ── */
    :root {
        --primary:       #1e40af;
        --primary-light: #3b82f6;
        --primary-glow:  rgba(59,130,246,0.15);
        --danger:        #dc2626;
        --warning:       #d97706;
        --success:       #16a34a;
        --info:          #0891b2;
        --bg-dark:       #0a0e1a;
        --bg-card:       #0f1629;
        --bg-surface:    #141d35;
        --bg-hover:      #1a2540;
        --border:        rgba(59,130,246,0.2);
        --border-bright: rgba(59,130,246,0.5);
        --text-primary:  #f0f4ff;
        --text-secondary:#94a3b8;
        --text-muted:    #64748b;
        --font-main:     'Inter', sans-serif;
        --font-mono:     'JetBrains Mono', monospace;
        --radius:        12px;
        --radius-sm:     8px;
        --shadow:        0 4px 24px rgba(0,0,0,0.4);
        --shadow-glow:   0 0 30px rgba(59,130,246,0.15);
    }

    /* ── Global Reset ── */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-dark) !important;
        font-family: var(--font-main) !important;
        color: var(--text-primary) !important;
    }

    /* ── Background with subtle grid pattern ── */
    [data-testid="stAppViewContainer"]::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background-image:
            linear-gradient(rgba(59,130,246,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(59,130,246,0.03) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
        z-index: 0;
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, header,
    [data-testid="stToolbar"],
    [data-testid="stDecoration"] { display: none !important; }

    /* ── Main content area ── */
    [data-testid="stMain"] > div {
        max-width: 1200px;
        margin: 0 auto;
        padding: 2rem 2rem 4rem !important;
    }

    /* ── Title ── */
    h1 {
        font-family: var(--font-main) !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        color: var(--text-primary) !important;
        text-align: center;
        letter-spacing: -0.5px;
        margin-bottom: 0.25rem !important;
    }

    h1 span { color: var(--primary-light); }

    /* ── Subheaders ── */
    h2, h3 {
        font-family: var(--font-main) !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.3px;
    }

    /* ── Markdown text ── */
    p, .stMarkdown p {
        color: var(--text-secondary) !important;
        font-size: 0.95rem !important;
        text-align: center;
        line-height: 1.7;
    }

    /* ── Divider ── */
    hr {
        border: none !important;
        border-top: 1px solid var(--border) !important;
        margin: 1.5rem 0 !important;
    }

    /* ── Tabs ── */
    [data-testid="stTabs"] > div:first-child {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 4px;
        gap: 4px;
        display: flex;
        justify-content: center;
    }

    [data-testid="stTabs"] button {
        font-family: var(--font-main) !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        color: var(--text-secondary) !important;
        background: transparent !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        padding: 0.6rem 1.8rem !important;
        transition: all 0.2s ease !important;
    }

    [data-testid="stTabs"] button:hover {
        color: var(--text-primary) !important;
        background: var(--bg-hover) !important;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--text-primary) !important;
        background: var(--primary) !important;
    }

    /* Remove the default red underline on active tab */
    [data-testid="stTabs"] button[aria-selected="true"]::after { display: none !important; }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        background: var(--bg-card) !important;
        border: 2px dashed var(--border) !important;
        border-radius: var(--radius) !important;
        padding: 2rem !important;
        text-align: center;
        transition: border-color 0.2s;
    }

    [data-testid="stFileUploader"]:hover {
        border-color: var(--border-bright) !important;
    }

    [data-testid="stFileUploader"] p {
        color: var(--text-secondary) !important;
        font-size: 0.9rem !important;
    }

    /* ── Checkboxes ── */
    [data-testid="stCheckbox"] label {
        color: var(--text-primary) !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
    }

    [data-testid="stCheckbox"] span[data-testid="stCheckboxWidget"] {
        border-color: var(--border-bright) !important;
    }

    /* ── Radio buttons ── */
    [data-testid="stRadio"] label {
        color: var(--text-secondary) !important;
        font-size: 0.9rem !important;
    }

    [data-testid="stRadio"] label:has(input:checked) {
        color: var(--primary-light) !important;
        font-weight: 500 !important;
    }

    /* ── Buttons ── */
    [data-testid="stButton"] > button {
        font-family: var(--font-main) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        background: var(--primary) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        padding: 0.65rem 2rem !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 0 20px rgba(59,130,246,0.3) !important;
        width: 100%;
    }

    [data-testid="stButton"] > button:hover {
        background: var(--primary-light) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 0 30px rgba(59,130,246,0.5) !important;
    }

    [data-testid="stButton"] > button:active {
        transform: translateY(0px) !important;
    }

    /* ── Download button ── */
    [data-testid="stDownloadButton"] > button {
        background: transparent !important;
        color: var(--primary-light) !important;
        border: 1px solid var(--border-bright) !important;
        box-shadow: none !important;
        width: auto !important;
    }

    [data-testid="stDownloadButton"] > button:hover {
        background: var(--primary-glow) !important;
        transform: none !important;
    }

    /* ── Spinner ── */
    [data-testid="stSpinner"] p {
        color: var(--primary-light) !important;
        font-size: 0.9rem !important;
        text-align: left !important;
    }

    /* ── Success / Info / Warning / Error messages ── */
    [data-testid="stAlert"] {
        border-radius: var(--radius) !important;
        border: 1px solid !important;
        font-family: var(--font-main) !important;
        font-size: 0.9rem !important;
    }

    [data-testid="stAlert"][data-baseweb="notification"][kind="info"] {
        background: rgba(8,145,178,0.1) !important;
        border-color: rgba(8,145,178,0.3) !important;
        color: #67e8f9 !important;
    }

    [data-testid="stAlert"][data-baseweb="notification"][kind="success"] {
        background: rgba(22,163,74,0.1) !important;
        border-color: rgba(22,163,74,0.3) !important;
        color: #86efac !important;
    }

    [data-testid="stAlert"][data-baseweb="notification"][kind="warning"] {
        background: rgba(217,119,6,0.1) !important;
        border-color: rgba(217,119,6,0.3) !important;
        color: #fcd34d !important;
    }

    [data-testid="stAlert"][data-baseweb="notification"][kind="error"] {
        background: rgba(220,38,38,0.1) !important;
        border-color: rgba(220,38,38,0.3) !important;
        color: #fca5a5 !important;
    }

    /* ── Dataframe / Table ── */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        overflow: hidden !important;
    }

    [data-testid="stDataFrame"] table {
        font-family: var(--font-main) !important;
        font-size: 0.85rem !important;
    }

    [data-testid="stDataFrame"] thead th {
        background: var(--bg-surface) !important;
        color: var(--primary-light) !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        border-bottom: 1px solid var(--border) !important;
        padding: 0.75rem 1rem !important;
    }

    [data-testid="stDataFrame"] tbody tr {
        border-bottom: 1px solid var(--border) !important;
    }

    [data-testid="stDataFrame"] tbody tr:hover td {
        background: var(--bg-hover) !important;
    }

    [data-testid="stDataFrame"] tbody td {
        color: var(--text-secondary) !important;
        padding: 0.65rem 1rem !important;
        background: var(--bg-card) !important;
    }

    /* ── Section headers ── */
    .section-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: var(--primary-glow);
        border: 1px solid var(--border-bright);
        border-radius: 20px;
        padding: 4px 16px;
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--primary-light);
        margin-bottom: 1rem;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    /* ── Code blocks ── */
    code, pre {
        font-family: var(--font-mono) !important;
        font-size: 0.85rem !important;
        background: var(--bg-surface) !important;
        color: var(--primary-light) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
    }

    /* ── Sidebar (if used) ── */
    [data-testid="stSidebar"] {
        background: var(--bg-card) !important;
        border-right: 1px solid var(--border) !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-dark); }
    ::-webkit-scrollbar-thumb { background: var(--border-bright); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--primary-light); }

    /* ── Column labels ── */
    .stMarkdown h3 {
        font-size: 1rem !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        margin-bottom: 0.5rem !important;
    }

    /* ── Caption text ── */
    .stCaption, [data-testid="stCaptionContainer"] p {
        color: var(--text-muted) !important;
        font-size: 0.8rem !important;
        text-align: center !important;
    }

    </style>
    """, unsafe_allow_html=True)


def render_header():
    """Renders the styled app header with logo and tagline."""
    st.markdown("""
    <div style="text-align:center; padding: 2rem 0 1rem;">
        <div style="display:inline-flex; align-items:center; gap:12px; margin-bottom:0.75rem;">
            <div style="width:44px; height:44px; background:linear-gradient(135deg,#1e40af,#3b82f6);
                        border-radius:10px; display:flex; align-items:center; justify-content:center;
                        font-size:22px; box-shadow:0 0 20px rgba(59,130,246,0.4);">🛡️</div>
            <h1 style="margin:0; font-size:2rem; font-weight:700; color:#f0f4ff; letter-spacing:-0.5px;">
                Log Analyzer and Anomaly Detector <span style="color:#3b82f6;">with LLM's</span>
            </h1>
        </div>
        <p style="color:#64748b; font-size:0.9rem; margin:0; letter-spacing:0.3px;
                   font-style:italic; font-weight:300;">
            Where log parsing meets deep learning—turning anomalies into actionable intelligence.
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_section_badge(icon: str, label: str):
    """Renders a small pill badge above a section."""
    st.markdown(
        f'<div class="section-badge">{icon}&nbsp; {label}</div>',
        unsafe_allow_html=True
    )


def render_empty_state():
    """Placeholder when no input has been provided."""
    st.markdown("""
    <div style="text-align:center; padding:4rem 2rem; margin-top:1rem;
                background:rgba(15,22,41,0.6); border:1px dashed rgba(59,130,246,0.2);
                border-radius:16px;">
        <div style="font-size:3rem; margin-bottom:1rem;">📋</div>
        <h3 style="color:#94a3b8; font-weight:500; font-size:1.1rem; margin-bottom:0.5rem;">
            No logs analyzed yet
        </h3>
        <p style="color:#475569; font-size:0.875rem; max-width:400px; margin:0 auto;">
            Upload a log file or collect live Windows logs to begin anomaly detection
        </p>
    </div>
    """, unsafe_allow_html=True)