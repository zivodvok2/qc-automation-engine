"""
DataSense — Survey QC Engine v2.0
Run: streamlit run app.py

Performance notes:
- QC pipeline only reruns when file changes or user clicks Rerun QC
- Tabs are lazy — only the active tab renders
- Column selection happens inside each tab via self-contained widgets
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) or "."))

import io
import json
from datetime import datetime

import streamlit as st
import pandas as pd

from ui.sidebar import render_sidebar, init_state, run_pipeline
from ui.onboarding import render_onboarding, init_onboarding
from ui.settings import get_theme_css, init_settings

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

html, body, [class*="css"] { font-family: var(--ds-mono, 'DM Mono', monospace); }
h1, h2, h3 { font-family: var(--ds-head, 'Syne', sans-serif) !important; }

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

section[data-testid="stSidebar"] {
    background: var(--ds-surface);
    border-right: 1px solid var(--ds-border);
}

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

[data-testid="stDataFrame"] {
    border: 1px solid var(--ds-border);
    border-radius: 6px;
}

.stButton > button {
    font-family: var(--ds-mono) !important;
    font-size: 11px !important;
    letter-spacing: 0.05em;
    border-radius: 6px !important;
    border: 1px solid var(--ds-border) !important;
    color: var(--ds-text) !important;
    background: var(--ds-surface2) !important;
    transition: border-color 0.15s;
}
.stButton > button:hover {
    border-color: var(--ds-accent) !important;
}
.stButton > button[kind="primary"] {
    background: var(--ds-accent) !important;
    color: #0b0c0f !important;
    border-color: var(--ds-accent) !important;
    font-weight: 600 !important;
}

div[data-testid="stExpander"] {
    border: 1px solid var(--ds-border) !important;
    border-radius: 8px !important;
    background: var(--ds-surface) !important;
}

div[data-testid="stExpander"] summary {
    color: var(--ds-text) !important;
    font-family: var(--ds-mono) !important;
    font-size: 12px !important;
    padding: 10px 14px !important;
}

hr { border-color: var(--ds-border) !important; }

[data-testid="stAlert"] {
    border-radius: 6px !important;
    font-family: var(--ds-mono) !important;
    font-size: 12px !important;
}

[data-testid="stFileUploaderDropzone"] {
    border: 1px dashed var(--ds-border) !important;
    border-radius: 6px !important;
    background: var(--ds-surface2) !important;
    padding: 12px !important;
}
[data-testid="stFileUploaderDropzone"] button {
    font-size: 11px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Init ──────────────────────────────────────────────────────────────────────
init_state()
init_onboarding()

# ── Sidebar ───────────────────────────────────────────────────────────────────
render_sidebar()

# ── Onboarding overlay ────────────────────────────────────────────────────────
render_onboarding()

# ── Landing page ──────────────────────────────────────────────────────────────
if st.session_state.df_clean is None:
    st.markdown("""
    <div style="text-align:center; padding:80px 40px 40px;">
        <div style="font-family:var(--ds-head);font-size:3rem;font-weight:800;
                    letter-spacing:-0.02em;">DataSense</div>
        <div style="font-size:10px;letter-spacing:0.25em;text-transform:uppercase;
                    color:var(--ds-accent);margin-top:6px;">Survey Quality Control Engine</div>
        <p style="color:var(--ds-text2);margin-top:20px;font-size:14px;
                  line-height:1.8;max-width:500px;margin-left:auto;margin-right:auto;">
            Upload a CSV or Excel file in the sidebar to get started.
            Upload multiple files for batch QC.
        </p>
    </div>
    """, unsafe_allow_html=True)

    features = [
        ("🔍", "Missing Values",       "Per-column detection"),
        ("📐", "Range Checks",         "Outlier detection"),
        ("🔗", "Logic Rules",          "Multi-condition + AI builder"),
        ("📋", "Straightlining",       "Repeated answer detection"),
        ("🕵️", "Fabrication",          "Sequence & variance"),
        ("👤", "Interviewer Risk",     "Weighted risk score (RAG)"),
        ("⚠️", "Consistency Checks",   "Cross-question contradictions"),
        ("📊", "Quota Monitoring",     "Target vs achieved, RAG"),
        ("🔁", "Wave Comparison",      "Drift detection across waves"),
        ("🔎", "Near-Duplicates",      "Phone match, pattern clones"),
        ("💬", "Verbatim QC",          "AI grammar scoring (Groq)"),
        ("📊", "EDA Charts",           "Multi-variable, Plotly"),
        ("📁", "Batch Processing",     "Multi-file combined QC"),
        ("💾", "Project Config",       "Save & reload settings"),
        ("🗂", "Column Mapping",       "Alias your column names"),
        ("📋", "Audit Trail",          "Timestamped QC log"),
    ]
    cols = st.columns(4)
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 4]:
            st.markdown(
                f"<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
                f"border-radius:10px;padding:16px;margin-bottom:12px;text-align:center;'>"
                f"<div style='font-size:1.4rem;margin-bottom:6px;'>{icon}</div>"
                f"<div style='font-family:var(--ds-head);font-weight:700;font-size:12px;"
                f"color:var(--ds-text);'>{title}</div>"
                f"<div style='font-size:10px;color:var(--ds-text2);margin-top:3px;'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    st.stop()

# ── Main content ──────────────────────────────────────────────────────────────
df       = st.session_state.df_clean
results  = st.session_state.qc_results
filename = st.session_state.filename


def _build_excel_report(df_clean, results) -> io.BytesIO:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        pd.DataFrame([r.summary() for r in results]).to_excel(
            w, sheet_name="QC Summary", index=False
        )
        frames = [
            r.flagged_rows.assign(_check=r.check_name, _sev=r.severity)
            for r in results if r.flag_count > 0
        ]
        if frames:
            pd.concat(frames, ignore_index=True).to_excel(
                w, sheet_name="Flagged Records", index=False
            )
        nc = df_clean.select_dtypes(include="number").columns
        if len(nc):
            df_clean[nc].describe().T.to_excel(w, sheet_name="EDA Numeric")
        df_clean.head(500).to_excel(w, sheet_name="Clean Data", index=False)
    out.seek(0)
    return out


def _build_pdf_report(df_clean, results) -> io.BytesIO | None:
    try:
        from core.pdf_reporter import generate_pdf, is_available
        if not is_available():
            return None
        # Pass interviewer risk table if available
        risk_df = st.session_state.get("_risk_df_cache")
        project_name = st.session_state.get("project_name", "")
        return generate_pdf(filename, df_clean, results, risk_df=risk_df, project_name=project_name)
    except Exception:
        return None


# ── Header row ────────────────────────────────────────────────────────────────
h1, h2, h3, h4 = st.columns([5, 1, 1, 1])
with h1:
    project = st.session_state.get("project_name", "")
    title   = f"{project} · {filename}" if project else filename
    st.markdown(
        f"<div style='display:flex;align-items:baseline;gap:12px;padding:4px 0;'>"
        f"<span style='font-family:var(--ds-head);font-weight:800;font-size:1.2rem;"
        f"color:var(--ds-text);'>{title}</span>"
        f"<span style='font-size:11px;color:var(--ds-text2);'>"
        f"{len(df):,} rows · {len(df.columns)} cols · "
        f"{datetime.now().strftime('%H:%M:%S')}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

stamp = datetime.now().strftime("%Y%m%d_%H%M")
base  = filename.rsplit(".", 1)[0]

with h2:
    st.download_button(
        "↓ Excel",
        data=_build_excel_report(df, results),
        file_name=f"DataSense_{base}_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )

with h3:
    pdf_buf = _build_pdf_report(df, results)
    if pdf_buf:
        st.download_button(
            "↓ PDF",
            data=pdf_buf,
            file_name=f"DataSense_{base}_{stamp}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.button(
            "↓ PDF",
            disabled=True,
            use_container_width=True,
            help="Install reportlab to enable PDF export: pip install reportlab",
        )

with h4:
    # Audit log download
    from core.audit_log import get_log_df
    log_df = get_log_df()
    if not log_df.empty:
        log_csv = io.BytesIO(log_df.to_csv(index=False).encode())
        st.download_button(
            "↓ Audit Log",
            data=log_csv,
            file_name=f"DataSense_audit_{stamp}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Download timestamped log of all QC runs this session",
        )

# ── Tabs ──────────────────────────────────────────────────────────────────────
from ui.tabs import (
    qc_tab, eda_tab, logic_tab, straightlining_tab, data_tab,
    interviewer_risk_tab, consistency_tab, quota_tab, wave_tab,
)

(
    tab_qc, tab_risk, tab_cons, tab_logic, tab_sl,
    tab_quota, tab_wave, tab_eda, tab_data, tab_cfg,
) = st.tabs([
    "QC Report", "Interviewer Risk", "Consistency",
    "Logic Checks", "Straightlining",
    "Quota Monitor", "Wave Comparison",
    "EDA", "Data Preview", "Config & Audit",
])

with tab_qc:
    qc_tab.render(df, results)

with tab_risk:
    interviewer_risk_tab.render(df, results)

with tab_cons:
    consistency_tab.render(df, results)

with tab_logic:
    logic_tab.render(df, results)

with tab_sl:
    straightlining_tab.render(df, results)

with tab_quota:
    quota_tab.render(df, results)

with tab_wave:
    wave_tab.render(df, results)

with tab_eda:
    eda_tab.render(df, results)

with tab_data:
    data_tab.render(df)

with tab_cfg:
    # Active config
    st.markdown("#### Active Config")
    st.json(st.session_state.rules_config)
    if st.session_state.custom_logic_rules:
        st.markdown("#### Custom Logic Rules")
        st.json(st.session_state.custom_logic_rules)
    if st.session_state.column_mappings:
        st.markdown("#### Column Mappings")
        st.json(st.session_state.column_mappings)

    # Audit trail
    st.divider()
    st.markdown("#### Audit Trail")
    st.caption(
        "Timestamped record of every QC run in this session. "
        "Download via the ↓ Audit Log button in the header."
    )
    from core.audit_log import get_log_df, get_log_detail, clear_log
    log_df = get_log_df()
    if log_df.empty:
        st.info("No runs logged yet. Run QC to start the audit trail.")
    else:
        st.dataframe(log_df, use_container_width=True, hide_index=True)

        # Detailed view of the most recent run
        with st.expander("Most recent run — check detail"):
            detail = get_log_detail(0)
            if detail.get("checks"):
                st.dataframe(
                    pd.DataFrame(detail["checks"]),
                    use_container_width=True,
                    hide_index=True,
                )
            if detail.get("config"):
                st.json(detail["config"])

        if st.button("Clear audit log", type="secondary"):
            clear_log()
            st.rerun()
