"""
ui/sidebar.py — DataSense sidebar

Handles file upload, basic QC settings, logic rule builder,
advanced check toggles, and settings panel.
"""

import streamlit as st
import pandas as pd
from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine
from ui.settings import render_settings, init_settings


def init_state():
    defaults = {
        "df_raw": None, "df_clean": None, "qc_results": None,
        "filename": None, "custom_logic_rules": [],
        "rules_config": _default_config(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _default_config() -> dict:
    return {
        "missing_threshold": 0.1,
        "range_rules": [],
        "logic_rules": [],
        "pattern_rules": [
            {"column": "phone", "pattern": r"^\+?[0-9 ()-]{7,15}$", "description": "Valid phone"},
            {"column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$",  "description": "Valid email"},
        ],
        "duplicate_check":                {"enabled": True,  "subset_columns": []},
        "interview_duration":             {"enabled": False, "column": "duration_minutes", "min_expected": 5, "max_expected": 120},
        "straightlining":                 {"enabled": False, "question_columns": [], "base_column": None, "threshold": 0.9, "min_questions": 3},
        "interviewer_duration_check":     {"enabled": False, "interviewer_column": "", "duration_column": "duration_minutes", "multiplier": 1.5, "min_interviews": 3},
        "interviewer_productivity_check": {"enabled": False, "interviewer_column": "", "multiplier": 1.5},
        "consent_eligibility_check":      {"enabled": False, "screener_column": "", "disqualify_operator": "!=", "disqualify_value": "", "subsequent_columns": []},
        "fabrication_check":              {"enabled": False, "id_column": None, "numeric_columns": [], "interviewer_column": None, "variance_threshold": 0.1, "sequence_run_length": 5},
        "verbatim_check":                 {"enabled": False, "verbatim_columns": [], "model": "llama3", "min_score": 2, "sample_size": 50},
    }


def run_pipeline(df: pd.DataFrame, filename: str):
    df_clean = DataCleaner().clean(df)
    cfg = dict(st.session_state.rules_config)
    cfg["logic_rules"] = cfg.get("logic_rules", []) + st.session_state.custom_logic_rules
    results = RuleEngine(config=cfg).run(df_clean)
    st.session_state.df_raw     = df
    st.session_state.df_clean   = df_clean
    st.session_state.qc_results = results
    st.session_state.filename   = filename


def render_sidebar():
    init_state()
    init_settings()

    with st.sidebar:
        # ── Branding ──────────────────────────────────────────────────────
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:10px;padding:4px 0 12px;">
                <div style="width:32px;height:32px;background:var(--ds-accent);border-radius:6px;
                            display:flex;align-items:center;justify-content:center;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                         stroke="#0b0c0f" stroke-width="2.5" stroke-linecap="round">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                    </svg>
                </div>
                <div>
                    <div style="font-family:var(--ds-head);font-weight:800;font-size:16px;
                                color:var(--ds-text);letter-spacing:0.02em;">DataSense</div>
                    <div style="font-size:10px;color:var(--ds-text2);letter-spacing:0.1em;">
                        SURVEY QC ENGINE</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Upload ────────────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:10px;letter-spacing:0.1em;text-transform:uppercase;"
            "color:var(--ds-text2);margin-bottom:6px;'>Data</div>",
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "Upload CSV or Excel",
            type=["csv", "xlsx", "xls"],
            label_visibility="collapsed",
        )
        if uploaded:
            with st.spinner("Loading..."):
                try:
                    df = DataLoader().load_from_buffer(uploaded)
                    run_pipeline(df, uploaded.name)
                    st.success(f"✓ {len(df):,} rows loaded")
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.session_state.df_clean is not None:
            df = st.session_state.df_clean
            st.caption(
                f"{len(df):,} rows · {len(df.columns)} cols · {st.session_state.filename}"
            )

        st.divider()

        # ── Basic QC settings ─────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:10px;letter-spacing:0.1em;text-transform:uppercase;"
            "color:var(--ds-text2);margin-bottom:6px;'>QC Settings</div>",
            unsafe_allow_html=True,
        )

        thr = st.slider("Missing threshold", 0.0, 1.0, 0.10, 0.01, format="%.0f%%",
                        help="Flag columns/rows with more than this % missing")
        st.session_state.rules_config["missing_threshold"] = thr

        dur_col = st.text_input("Duration column", value="duration_minutes",
                                help="Column holding interview duration in minutes")
        min_dur = st.number_input("Min duration (mins)", value=5,   min_value=0)
        max_dur = st.number_input("Max duration (mins)", value=120, min_value=1)
        st.session_state.rules_config["interview_duration"] = {
            "enabled": bool(dur_col), "column": dur_col,
            "min_expected": min_dur, "max_expected": max_dur,
        }

        st.divider()

        # ── Interviewer checks ────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:10px;letter-spacing:0.1em;text-transform:uppercase;"
            "color:var(--ds-text2);margin-bottom:6px;'>Interviewer Checks</div>",
            unsafe_allow_html=True,
        )
        int_col = st.text_input(
            "Interviewer column", placeholder="interviewer_id",
            help="Column identifying each interviewer"
        )

        id_on = st.toggle("Duration anomaly", value=False,
                          help="Flag interviewers whose average duration is an outlier vs peers")
        st.session_state.rules_config["interviewer_duration_check"] = {
            "enabled": id_on and bool(int_col and dur_col),
            "interviewer_column": int_col, "duration_column": dur_col,
            "multiplier": 1.5, "min_interviews": 3,
        }

        ip_on = st.toggle("Productivity outliers", value=False,
                          help="Flag interviewers completing unusually many or few interviews")
        st.session_state.rules_config["interviewer_productivity_check"] = {
            "enabled": ip_on and bool(int_col),
            "interviewer_column": int_col, "multiplier": 1.5,
        }

        st.divider()

        # ── Consent / eligibility ─────────────────────────────────────────
        ce_on = st.toggle("Consent / eligibility check", value=False,
                          help="Flag disqualified respondents who still have data")
        if ce_on:
            sc_col  = st.text_input("Screener column", placeholder="consent")
            dq_op   = st.selectbox("Disqualify if", ["!=","==","<",">","<=",">="])
            dq_val  = st.text_input("Value", placeholder="Yes")
            sub_raw = st.text_input("Subsequent columns", placeholder="Q1, Q2, Q3",
                                    help="Columns that should be empty for disqualified respondents")
            st.session_state.rules_config["consent_eligibility_check"] = {
                "enabled": bool(sc_col and dq_val),
                "screener_column": sc_col, "disqualify_operator": dq_op,
                "disqualify_value": dq_val,
                "subsequent_columns": [c.strip() for c in sub_raw.split(",") if c.strip()],
            }
        else:
            st.session_state.rules_config["consent_eligibility_check"] = {
                "enabled": False, "screener_column": "", "disqualify_operator": "!=",
                "disqualify_value": "", "subsequent_columns": [],
            }

        st.divider()

        # ── Fabrication ───────────────────────────────────────────────────
        fab_on = st.toggle("Fabrication detection", value=False,
                           help="Detect sequential IDs and low-variance numeric responses")
        if fab_on:
            fab_id  = st.text_input("Respondent ID column", placeholder="respondent_id")
            fab_num = st.text_input("Numeric columns (comma-sep)",
                                    placeholder="Q1, Q2, Q3",
                                    help="Check these for suspiciously low variance per interviewer")
            fab_vt  = st.slider("Variance threshold", 0.01, 0.5, 0.1, 0.01)
            fab_rl  = st.number_input("Sequential run length", value=5, min_value=2)
            st.session_state.rules_config["fabrication_check"] = {
                "enabled": True,
                "id_column": fab_id or None,
                "numeric_columns": [c.strip() for c in fab_num.split(",") if c.strip()],
                "interviewer_column": int_col or None,
                "variance_threshold": fab_vt,
                "sequence_run_length": int(fab_rl),
            }
        else:
            st.session_state.rules_config["fabrication_check"] = {"enabled": False}

        st.divider()

        # ── Verbatim ──────────────────────────────────────────────────────
        verb_on = st.toggle("Verbatim quality check", value=False,
                            help="Use local Ollama LLM to check grammar, coherence, and relevance")
        if verb_on:
            vb_cols_raw = st.text_input("Verbatim columns (comma-sep)",
                                        placeholder="Q10_text, comments")
            vb_sample   = st.number_input("Sample size", value=50, min_value=5, max_value=500,
                                          help="Number of responses to evaluate (for speed)")
            vb_min_score = st.slider("Min quality score (1–5)", 1, 5, 2,
                                     help="Flag responses scoring below this on any dimension")
            st.session_state.rules_config["verbatim_check"] = {
                "enabled": True,
                "verbatim_columns": [c.strip() for c in vb_cols_raw.split(",") if c.strip()],
                "model": st.session_state.get("ds_ollama_model", "llama3"),
                "min_score": vb_min_score,
                "sample_size": int(vb_sample),
            }
        else:
            st.session_state.rules_config["verbatim_check"] = {"enabled": False}

        # ── Rerun ─────────────────────────────────────────────────────────
        if st.session_state.df_clean is not None:
            st.divider()
            if st.button("↺ Rerun QC", use_container_width=True, type="primary"):
                with st.spinner("Running..."):
                    run_pipeline(st.session_state.df_raw, st.session_state.filename)
                st.success("Done")

        # ── Settings panel ────────────────────────────────────────────────
        render_settings()
