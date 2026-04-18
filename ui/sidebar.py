"""
ui/sidebar.py — DataSense sidebar

Performance notes:
- Pipeline only reruns when file changes or user clicks Rerun QC
- File hash (MD5) used as cache key so re-uploading the same file is instant
- Config changes are staged; only applied on Rerun QC
"""

import hashlib
import json
from datetime import datetime

import streamlit as st
import pandas as pd

from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine
from core.audit_log import log_run, set_last_row_count
from ui.settings import render_settings, init_settings


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(df: pd.DataFrame, filename: str):
    """Run QC pipeline and store results in session state."""
    # Apply column mappings before cleaning
    mappings = st.session_state.get("column_mappings", {})
    if mappings:
        df = df.rename(columns=mappings)

    df_clean = DataCleaner().clean(df)
    cfg = _build_cfg()

    results = RuleEngine(config=cfg).run(df_clean)

    st.session_state.df_raw     = df
    st.session_state.df_clean   = df_clean
    st.session_state.qc_results = results
    st.session_state.filename   = filename

    # Audit trail
    log_run(filename, results, cfg)
    set_last_row_count(len(df_clean))


def _build_cfg() -> dict:
    rc = st.session_state.get("rules_config", _default_config())
    cfg = dict(rc)
    cfg["logic_rules"]       = cfg.get("logic_rules", []) + st.session_state.get("custom_logic_rules", [])
    cfg["consistency_rules"] = st.session_state.get("consistency_rules", [])
    return cfg


def init_state():
    defaults = {
        "df_raw": None,
        "df_clean": None,
        "qc_results": None,
        "filename": None,
        "custom_logic_rules": [],
        "consistency_rules": [],
        "rules_config": _default_config(),
        "column_mappings": {},
        "audit_log": [],
        "project_name": "",
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
        "interview_duration":             {"enabled": False, "column": "duration_minutes", "min_expected": 5,  "max_expected": 120},
        "straightlining":                 {"enabled": False, "question_columns": [], "base_column": None, "threshold": 0.9, "min_questions": 3},
        "interviewer_duration_check":     {"enabled": False, "interviewer_column": "", "duration_column": "duration_minutes", "multiplier": 1.5, "min_interviews": 3},
        "interviewer_productivity_check": {"enabled": False, "interviewer_column": "", "multiplier": 1.5},
        "consent_eligibility_check":      {"enabled": False, "screener_column": "", "disqualify_operator": "!=", "disqualify_value": "", "subsequent_columns": []},
        "fabrication_check":              {"enabled": False, "id_column": None, "numeric_columns": [], "interviewer_column": None, "variance_threshold": 0.1, "sequence_run_length": 5},
        "near_duplicate_check":           {"enabled": False, "shared_id_column": None, "demographic_columns": [], "response_columns": [], "min_demo_repeats": 3, "max_diff_columns": 1},
        "verbatim_check":                 {"enabled": False, "verbatim_columns": [], "model": "llama3-8b-8192", "min_score": 2, "sample_size": 50},
    }


# ── Sidebar render ────────────────────────────────────────────────────────────

def render_sidebar():
    init_state()
    init_settings()

    with st.sidebar:

        # ── Branding ──────────────────────────────────────────────────────
        st.markdown(
            """<div style="padding:8px 0 14px;">
                <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:18px;
                            color:var(--ds-text);letter-spacing:0.02em;">
                    <span style="color:var(--ds-accent);">■</span> DataSense
                </div>
                <div style="font-size:9px;color:var(--ds-text2);letter-spacing:0.15em;
                            text-transform:uppercase;margin-top:2px;">
                    Survey QC Engine
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Upload (single or batch) ──────────────────────────────────────
        st.caption("UPLOAD DATA")
        uploaded_files = st.file_uploader(
            "Upload",
            type=["csv", "xlsx", "xls"],
            label_visibility="collapsed",
            accept_multiple_files=True,
            help="Upload one file or multiple files for batch QC. Supports CSV and Excel.",
        )

        if uploaded_files:
            file_hash = hashlib.md5(
                b"||".join(f.getvalue() for f in uploaded_files)
            ).hexdigest()

            if st.session_state.get("_last_file_hash") != file_hash:
                with st.spinner("Loading data…"):
                    try:
                        if len(uploaded_files) == 1:
                            df = DataLoader().load_from_buffer(uploaded_files[0])
                            filename = uploaded_files[0].name
                        else:
                            dfs = []
                            for f in uploaded_files:
                                df_i = DataLoader().load_from_buffer(f)
                                df_i["_source_file"] = f.name
                                dfs.append(df_i)
                            df = pd.concat(dfs, ignore_index=True)
                            filename = f"Batch — {len(uploaded_files)} files"

                        run_pipeline(df, filename)
                        st.session_state["_last_file_hash"] = file_hash

                        n = len(st.session_state.df_clean)
                        label = (
                            f"✓ {n:,} rows · {len(st.session_state.df_clean.columns)} cols"
                            if len(uploaded_files) == 1
                            else f"✓ {n:,} rows combined from {len(uploaded_files)} files"
                        )
                        st.success(label)
                    except Exception as e:
                        st.error(f"Error loading file(s): {e}")
            else:
                df = st.session_state.df_clean
                if df is not None:
                    n_files = len(uploaded_files)
                    label = (
                        f"{len(df):,} rows · {len(df.columns)} cols · {uploaded_files[0].name}"
                        if n_files == 1
                        else f"{len(df):,} rows combined · {n_files} files"
                    )
                    st.caption(label)

            # ── Auto column detection ──────────────────────────────────────
            df_loaded = st.session_state.get("df_clean")
            if df_loaded is not None:
                from core.groq_utils import groq_available, groq_json
                if groq_available():
                    if st.button("🤖 Auto-detect columns", use_container_width=True,
                                 help="Use AI to suggest interviewer ID, duration, phone, and respondent ID columns"):
                        with st.spinner("Detecting columns…"):
                            try:
                                cols = df_loaded.columns.tolist()
                                samples = {}
                                for c in cols[:40]:
                                    vals = df_loaded[c].dropna().astype(str).head(3).tolist()
                                    samples[c] = vals
                                suggestion = groq_json(
                                    prompt=(
                                        "Analyse these survey dataset column names and sample values.\n\n"
                                        f"Columns and samples: {json.dumps(samples, default=str)}\n\n"
                                        "Return a JSON object identifying which column is most likely each role "
                                        "(use null if not found):\n"
                                        '{"interviewer_id": "col_name_or_null", '
                                        '"respondent_id": "col_name_or_null", '
                                        '"duration_minutes": "col_name_or_null", '
                                        '"phone": "col_name_or_null"}\n\n'
                                        "Only include columns that actually exist in the list above. "
                                        "Return ONLY the JSON."
                                    ),
                                    system="You are a survey data column classifier. Return only valid JSON.",
                                )
                                applied = []
                                rc = st.session_state.rules_config
                                if suggestion.get("interviewer_id"):
                                    col = suggestion["interviewer_id"]
                                    if col in df_loaded.columns:
                                        for key in ("interviewer_duration_check", "interviewer_productivity_check"):
                                            rc.setdefault(key, {})["interviewer_column"] = col
                                        applied.append(f"Interviewer ID → {col}")
                                if suggestion.get("duration_minutes"):
                                    col = suggestion["duration_minutes"]
                                    if col in df_loaded.columns:
                                        rc.setdefault("interview_duration", {})["column"] = col
                                        rc["interview_duration"]["enabled"] = True
                                        applied.append(f"Duration → {col}")
                                if suggestion.get("respondent_id"):
                                    col = suggestion["respondent_id"]
                                    if col in df_loaded.columns:
                                        rc.setdefault("fabrication_check", {})["id_column"] = col
                                        applied.append(f"Respondent ID → {col}")
                                if suggestion.get("phone"):
                                    col = suggestion["phone"]
                                    if col in df_loaded.columns:
                                        rc.setdefault("near_duplicate_check", {})["shared_id_column"] = col
                                        applied.append(f"Phone → {col}")
                                if applied:
                                    st.success("Auto-detected: " + " · ".join(applied))
                                    st.rerun()
                                else:
                                    st.info("Could not identify standard columns automatically.")
                            except Exception as e:
                                st.warning(f"Auto-detection failed: {e}")

        st.divider()

        # ── Column Mapping ────────────────────────────────────────────────
        with st.expander("🗂 Column Mapping / Aliasing"):
            st.caption(
                "Map your column names to standard names before QC runs. "
                "e.g. 'INT_CODE' → 'interviewer_id'"
            )
            mappings: dict = st.session_state.column_mappings

            # Show existing mappings
            to_delete = []
            for orig, target in list(mappings.items()):
                col1, col2, col3 = st.columns([5, 5, 1])
                col1.caption(orig)
                col2.caption(f"→ {target}")
                if col3.button("✕", key=f"del_map_{orig}", help="Remove mapping"):
                    to_delete.append(orig)
            for k in to_delete:
                del st.session_state.column_mappings[k]

            # Add new mapping
            ca, cb = st.columns(2)
            from_col = ca.text_input("Your column",   placeholder="INT_CODE",       key="map_from")
            to_col   = cb.text_input("Standard name", placeholder="interviewer_id",  key="map_to")
            if st.button("Add mapping", use_container_width=True):
                if from_col and to_col:
                    st.session_state.column_mappings[from_col] = to_col
                    st.rerun()
                else:
                    st.warning("Enter both column names.")

        # ── Project Config Save / Load ────────────────────────────────────
        with st.expander("💾 Project Config"):
            st.session_state.project_name = st.text_input(
                "Project name",
                value=st.session_state.get("project_name", ""),
                placeholder="e.g. Ipsos Kenya Wave 3",
                key="proj_name_input",
            )

            # Save current config
            project_data = {
                "project_name":   st.session_state.project_name or "Untitled",
                "saved_at":       datetime.now().isoformat(),
                "rules_config":   st.session_state.rules_config,
                "column_mappings": st.session_state.column_mappings,
            }
            st.download_button(
                "↓ Save project config",
                data=json.dumps(project_data, indent=2, default=str),
                file_name=f"{st.session_state.project_name or 'project'}.datasense.json",
                mime="application/json",
                use_container_width=True,
                help="Downloads current settings as a JSON file you can reload later",
            )

            # Load saved config
            proj_file = st.file_uploader(
                "Load project config",
                type=["json"],
                key="proj_load",
                help="Upload a previously saved .datasense.json project file",
                label_visibility="visible",
            )
            if proj_file:
                try:
                    loaded = json.loads(proj_file.read())
                    if "rules_config" in loaded:
                        st.session_state.rules_config = loaded["rules_config"]
                    if "column_mappings" in loaded:
                        st.session_state.column_mappings = loaded["column_mappings"]
                    if "project_name" in loaded:
                        st.session_state.project_name = loaded["project_name"]
                    st.success(
                        f"Loaded: **{loaded.get('project_name', 'Unnamed')}** "
                        f"(saved {loaded.get('saved_at', '')[:10]}). "
                        "Click ↺ Rerun QC to apply."
                    )
                except Exception as e:
                    st.error(f"Failed to load project: {e}")

        st.divider()

        # ── Basic QC Settings ─────────────────────────────────────────────
        st.caption("QC SETTINGS")

        thr = st.slider(
            "Missing threshold", 0.0, 1.0,
            float(st.session_state.rules_config.get("missing_threshold", 0.10)),
            0.01, format="%.0f%%",
            help="Flag rows/columns where missing values exceed this %",
        )
        st.session_state.rules_config["missing_threshold"] = thr

        dur_col = st.text_input(
            "Duration column",
            value=st.session_state.rules_config.get("interview_duration", {}).get("column", "duration_minutes"),
            help="Column holding interview duration (minutes)",
        )
        c1, c2 = st.columns(2)
        min_dur = c1.number_input("Min (mins)", value=int(st.session_state.rules_config.get("interview_duration", {}).get("min_expected", 5)),   min_value=0)
        max_dur = c2.number_input("Max (mins)", value=int(st.session_state.rules_config.get("interview_duration", {}).get("max_expected", 120)), min_value=1)
        st.session_state.rules_config["interview_duration"] = {
            "enabled": bool(dur_col),
            "column": dur_col,
            "min_expected": min_dur,
            "max_expected": max_dur,
        }

        st.divider()

        # ── Interviewer Checks ────────────────────────────────────────────
        st.caption("INTERVIEWER CHECKS")
        int_col = st.text_input(
            "Interviewer column",
            value=st.session_state.rules_config.get("interviewer_duration_check", {}).get("interviewer_column", ""),
            placeholder="e.g. interviewer_id",
            help="Column that identifies each interviewer",
        )

        id_on = st.toggle(
            "Duration anomaly",
            value=st.session_state.rules_config.get("interviewer_duration_check", {}).get("enabled", False),
            help="Flag interviewers whose mean duration is an outlier vs peers (IQR)",
        )
        st.session_state.rules_config["interviewer_duration_check"] = {
            "enabled":            id_on and bool(int_col and dur_col),
            "interviewer_column": int_col,
            "duration_column":    dur_col,
            "multiplier":         1.5,
            "min_interviews":     3,
        }

        ip_on = st.toggle(
            "Productivity outliers",
            value=st.session_state.rules_config.get("interviewer_productivity_check", {}).get("enabled", False),
            help="Flag interviewers completing unusually many or few interviews (IQR)",
        )
        st.session_state.rules_config["interviewer_productivity_check"] = {
            "enabled":            ip_on and bool(int_col),
            "interviewer_column": int_col,
            "multiplier":         1.5,
        }

        st.divider()

        # ── Consent / Eligibility ─────────────────────────────────────────
        ce_cfg  = st.session_state.rules_config.get("consent_eligibility_check", {})
        ce_on   = st.toggle(
            "Consent / eligibility check",
            value=ce_cfg.get("enabled", False),
            help="Flag disqualified respondents who still have data in survey questions",
        )
        if ce_on:
            sc_col  = st.text_input("Screener column", value=ce_cfg.get("screener_column", ""), placeholder="consent")
            dq_op   = st.selectbox("Disqualify if column is", ["!=","==","<",">","<=",">="],
                                   index=["!=","==","<",">","<=",">="].index(ce_cfg.get("disqualify_operator","!=")))
            dq_val  = st.text_input("Disqualify value", value=ce_cfg.get("disqualify_value", ""), placeholder="Yes")
            sub_raw = st.text_input(
                "Subsequent columns (comma-sep)",
                value=", ".join(ce_cfg.get("subsequent_columns", [])),
                placeholder="Q1, Q2, Q3",
            )
            st.session_state.rules_config["consent_eligibility_check"] = {
                "enabled": bool(sc_col and dq_val),
                "screener_column": sc_col,
                "disqualify_operator": dq_op,
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
        fab_cfg = st.session_state.rules_config.get("fabrication_check", {})
        fab_on  = st.toggle(
            "Fabrication detection",
            value=fab_cfg.get("enabled", False),
            help="Detect sequential respondent IDs and suspiciously uniform numeric responses",
        )
        if fab_on:
            fab_id  = st.text_input("Respondent ID column", value=fab_cfg.get("id_column") or "", placeholder="respondent_id")
            fab_num = st.text_input(
                "Numeric columns (comma-sep)",
                value=", ".join(fab_cfg.get("numeric_columns", [])),
                placeholder="Q1, Q2, Q3",
                help="Check these for low variance per interviewer",
            )
            c1, c2  = st.columns(2)
            fab_vt  = c1.slider("Variance thr.", 0.01, 0.5, float(fab_cfg.get("variance_threshold", 0.1)), 0.01)
            fab_rl  = c2.number_input("Run length", value=int(fab_cfg.get("sequence_run_length", 5)), min_value=2)
            st.session_state.rules_config["fabrication_check"] = {
                "enabled":           True,
                "id_column":         fab_id or None,
                "numeric_columns":   [c.strip() for c in fab_num.split(",") if c.strip()],
                "interviewer_column": int_col or None,
                "variance_threshold": fab_vt,
                "sequence_run_length": int(fab_rl),
            }
        else:
            st.session_state.rules_config["fabrication_check"] = {"enabled": False}

        st.divider()

        # ── Near-duplicate detection ──────────────────────────────────────
        nd_cfg = st.session_state.rules_config.get("near_duplicate_check", {})
        nd_on  = st.toggle(
            "Near-duplicate detection",
            value=nd_cfg.get("enabled", False),
            help="Detect fabricated interviews disguised as different respondents",
        )
        if nd_on:
            nd_phone = st.text_input(
                "Shared ID column (phone/email)",
                value=nd_cfg.get("shared_id_column", ""),
                placeholder="e.g. phone_number",
                help="Flag same phone/email appearing under different respondent IDs",
            )
            nd_demo_raw = st.text_input(
                "Demographic columns (comma-sep)",
                value=", ".join(nd_cfg.get("demographic_columns", [])),
                placeholder="age, gender, location",
                help="Flag demographic combos that repeat suspiciously often",
            )
            nd_resp_raw = st.text_input(
                "Response columns (comma-sep)",
                value=", ".join(nd_cfg.get("response_columns", [])),
                placeholder="Q1, Q2, Q3, Q4, Q5",
                help="Flag rows with near-identical response patterns",
            )
            c1, c2 = st.columns(2)
            nd_min_rep  = c1.number_input("Min demo repeats", value=int(nd_cfg.get("min_demo_repeats", 3)), min_value=2)
            nd_max_diff = c2.number_input("Max diff columns", value=int(nd_cfg.get("max_diff_columns", 1)), min_value=1, max_value=5)
            st.session_state.rules_config["near_duplicate_check"] = {
                "enabled":             True,
                "respondent_id_column": fab_id if fab_on else nd_cfg.get("respondent_id_column", ""),
                "shared_id_column":    nd_phone or None,
                "demographic_columns": [c.strip() for c in nd_demo_raw.split(",") if c.strip()],
                "response_columns":    [c.strip() for c in nd_resp_raw.split(",") if c.strip()],
                "min_demo_repeats":    int(nd_min_rep),
                "max_diff_columns":    int(nd_max_diff),
            }
        else:
            st.session_state.rules_config["near_duplicate_check"] = {"enabled": False}

        st.divider()

        # ── Verbatim (Groq) ───────────────────────────────────────────────
        verb_cfg = st.session_state.rules_config.get("verbatim_check", {})
        verb_on  = st.toggle(
            "Verbatim quality check",
            value=verb_cfg.get("enabled", False),
            help="Use Groq AI to score grammar, coherence, and relevance of open-ended responses",
        )
        if verb_on:
            vb_cols_raw = st.text_input(
                "Verbatim columns (comma-sep)",
                value=", ".join(verb_cfg.get("verbatim_columns", [])),
                placeholder="Q10_text, comments",
            )
            c1, c2 = st.columns(2)
            vb_sample    = c1.number_input("Sample size", value=int(verb_cfg.get("sample_size", 50)), min_value=5, max_value=500)
            vb_min_score = c2.slider("Min score", 1, 5, int(verb_cfg.get("min_score", 2)))
            st.session_state.rules_config["verbatim_check"] = {
                "enabled":          True,
                "verbatim_columns": [c.strip() for c in vb_cols_raw.split(",") if c.strip()],
                "model":            "llama3-8b-8192",
                "min_score":        vb_min_score,
                "sample_size":      int(vb_sample),
            }
        else:
            st.session_state.rules_config["verbatim_check"] = {"enabled": False}

        # ── Rerun QC ──────────────────────────────────────────────────────
        if st.session_state.df_clean is not None:
            st.divider()
            if st.button("↺ Rerun QC", use_container_width=True, type="primary"):
                with st.spinner("Running checks…"):
                    run_pipeline(st.session_state.df_raw, st.session_state.filename)
                st.success("Done")

        # ── Settings ──────────────────────────────────────────────────────
        render_settings()
