"""
DataSense — Survey QC Engine
Run: streamlit run app.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) or "."))

import io
from datetime import datetime

import streamlit as st
import pandas as pd

from ui.sidebar import render_sidebar, init_state, run_pipeline
from ui.onboarding import render_onboarding, init_onboarding
from ui.settings import get_theme_css, init_settings
from ui.components.drag_drop import column_panel

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DataSense",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme + global CSS ────────────────────────────────────────────────────────
init_settings()
theme_css = get_theme_css(st.session_state.get("ds_theme", "dark"))

st.markdown(theme_css, unsafe_allow_html=True)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: var(--ds-mono, 'DM Mono', monospace);
}
h1, h2, h3 {
    font-family: var(--ds-head, 'Syne', sans-serif) !important;
}

/* Metric cards */
[data-testid="metric-container"] {
    background: var(--ds-surface);
    border: 1px solid var(--ds-border);
    border-radius: 8px;
    padding: 14px 18px;
}
[data-testid="metric-container"] label {
    font-size: 10px !important;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ds-text2) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: var(--ds-head) !important;
    font-weight: 800 !important;
    font-size: 1.9rem !important;
    color: var(--ds-text) !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--ds-surface);
    border-right: 1px solid var(--ds-border);
}
section[data-testid="stSidebar"] * {
    font-family: var(--ds-mono) !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-family: var(--ds-mono) !important;
    font-size: 11px !important;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--ds-text2) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--ds-text) !important;
    border-bottom-color: var(--ds-accent) !important;
}

/* DataFrames */
[data-testid="stDataFrame"] {
    border: 1px solid var(--ds-border);
    border-radius: 6px;
}

/* Buttons */
.stButton > button {
    font-family: var(--ds-mono) !important;
    font-size: 11px !important;
    letter-spacing: 0.05em;
    border-radius: 6px !important;
    border: 1px solid var(--ds-border) !important;
    color: var(--ds-text) !important;
    background: var(--ds-surface2) !important;
    transition: border-color 0.15s, background 0.15s;
}
.stButton > button:hover {
    border-color: var(--ds-accent) !important;
    background: var(--ds-surface) !important;
}
.stButton > button[kind="primary"] {
    background: var(--ds-accent) !important;
    color: #0b0c0f !important;
    border-color: var(--ds-accent) !important;
    font-weight: 600 !important;
}

/* Inputs */
input[type="text"], input[type="number"], textarea, select {
    background: var(--ds-surface2) !important;
    border: 1px solid var(--ds-border) !important;
    border-radius: 4px !important;
    color: var(--ds-text) !important;
    font-family: var(--ds-mono) !important;
    font-size: 12px !important;
}
input:focus, textarea:focus {
    border-color: var(--ds-accent) !important;
    outline: none !important;
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--ds-accent) 20%, transparent) !important;
}

/* Drop zone hover */
.ds-drop-active {
    border-color: var(--ds-accent) !important;
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--ds-accent) 20%, transparent);
}

/* Expanders */
div[data-testid="stExpander"] {
    border: 1px solid var(--ds-border) !important;
    border-radius: 8px !important;
    background: var(--ds-surface) !important;
}
div[data-testid="stExpander"] summary {
    color: var(--ds-text) !important;
    font-family: var(--ds-mono) !important;
    font-size: 12px !important;
}

/* Divider */
hr { border-color: var(--ds-border) !important; }

/* Success / warning / error */
[data-testid="stAlert"] {
    border-radius: 6px !important;
    font-family: var(--ds-mono) !important;
    font-size: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Init ──────────────────────────────────────────────────────────────────────
init_state()
init_onboarding()

# ── Sidebar ───────────────────────────────────────────────────────────────────
render_sidebar()

# ── Onboarding ────────────────────────────────────────────────────────────────
render_onboarding()

# ── Landing page (no data) ────────────────────────────────────────────────────
if st.session_state.df_clean is None:
    st.markdown("""
    <div style="text-align:center; padding:80px 40px 40px;">
        <div style="font-family:var(--ds-head);font-size:3rem;font-weight:800;
                    color:var(--ds-text);letter-spacing:-0.02em;">DataSense</div>
        <div style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;
                    color:var(--ds-accent);margin-top:4px;">Survey Quality Control Engine</div>
        <p style="color:var(--ds-text2);margin-top:20px;font-size:14px;line-height:1.8;
                  max-width:520px;margin-left:auto;margin-right:auto;">
            Upload a CSV or Excel file using the sidebar to run automated quality
            control checks, exploratory analysis, and generate a structured report.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Feature cards
    features = [
        ("🔍", "Missing Values",  "Per-column detection & rate"),
        ("📐", "Range Checks",    "Outliers & bound violations"),
        ("🔗", "Logic Rules",     "Multi-condition drag-and-drop"),
        ("📋", "Straightlining",  "Repeated answer detection"),
        ("🕵️", "Fabrication",    "Sequence & variance checks"),
        ("👤", "Interviewer QC",  "Duration & productivity"),
        ("💬", "Verbatim QC",     "Grammar via local LLM"),
        ("📊", "EDA Charts",      "Multi-variable, multiple chart types"),
    ]
    cols = st.columns(4)
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 4]:
            st.markdown(
                f"<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
                f"border-radius:10px;padding:18px 16px;margin-bottom:12px;text-align:center;'>"
                f"<div style='font-size:1.5rem;margin-bottom:8px;'>{icon}</div>"
                f"<div style='font-family:var(--ds-head);font-weight:700;font-size:13px;"
                f"color:var(--ds-text);margin-bottom:4px;'>{title}</div>"
                f"<div style='font-size:11px;color:var(--ds-text2);'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    st.stop()


# ── Main content ──────────────────────────────────────────────────────────────
df       = st.session_state.df_clean
results  = st.session_state.qc_results
filename = st.session_state.filename

# ── Header ────────────────────────────────────────────────────────────────────
# Locate the _build_report function in your app.py (usually near the bottom)

def _build_report(df, results):
    """
    Builds a consolidated CSV report for the Streamlit UI.
    Replaces ExcelWriter to avoid openpyxl dependency.
    """
    import pandas as pd
    import io

    all_flagged = []
    for res in results:
        # Check if flagged_rows exists and has data
        if hasattr(res, 'flagged_rows') and not res.flagged_rows.empty:
            tmp = res.flagged_rows.copy()
            tmp["QC_Check_Name"] = res.check_name
            tmp["QC_Issue_Type"] = res.issue_type
            tmp["QC_Severity"] = res.severity
            all_flagged.append(tmp)
    
    if all_flagged:
        final_df = pd.concat(all_flagged, ignore_index=True)
    else:
        # Return a simple CSV saying no issues were found
        final_df = pd.DataFrame([{"System Message": "No QC issues flagged in this run."}])

    # Convert DataFrame to CSV string and then to bytes
    return final_df.to_csv(index=False).encode('utf-8')




h1, h2 = st.columns([5, 1])
with h1:
    st.markdown(
        f"<div style='display:flex;align-items:baseline;gap:12px;'>"
        f"<span style='font-family:var(--ds-head);font-weight:800;font-size:1.3rem;"
        f"color:var(--ds-text);'>{filename}</span>"
        f"<span style='font-size:11px;color:var(--ds-text2);'>"
        f"{len(df):,} rows · {len(df.columns)} cols · "
        f"Last run: {datetime.now().strftime('%H:%M:%S')}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
with h2:
    # --- In your Streamlit UI section (where the button is rendered) ---

# Replace the existing st.download_button with this:
st.download_button(
    label="📥 Download Detailed QC Report (CSV)",
    data=_build_report(df, results),
    file_name=f"datasense_report_{timestamp_str()}.csv",
    mime="text/csv",
)
    )

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ── Two-column layout: column panel + tabs ────────────────────────────────────
panel_col, content_col = st.columns([1, 5])

with panel_col:
    st.markdown(
        "<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
        "border-radius:8px;padding:12px;height:100%;min-height:400px;'>",
        unsafe_allow_html=True,
    )
    column_panel(df.columns.tolist())
    st.markdown("</div>", unsafe_allow_html=True)

with content_col:
    from ui.tabs import qc_tab, eda_tab, logic_tab, straightlining_tab, data_tab

    tab_qc, tab_logic, tab_sl, tab_eda, tab_data, tab_cfg = st.tabs([
        "QC Report", "Logic Checks", "Straightlining", "EDA", "Data Preview", "Config"
    ])

    with tab_qc:
        qc_tab.render(df, results)

    with tab_logic:
        logic_tab.render(df, results)

    with tab_sl:
        straightlining_tab.render(df, results)

    with tab_eda:
        eda_tab.render(df, results)

    with tab_data:
        data_tab.render(df)

    with tab_cfg:
        st.markdown("#### Active Config")
        st.json(st.session_state.rules_config)
        st.markdown("#### Custom Logic Rules")
        if st.session_state.custom_logic_rules:
            st.json(st.session_state.custom_logic_rules)
        else:
            st.caption("No custom logic rules added yet.")
