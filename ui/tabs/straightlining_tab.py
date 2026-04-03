"""
ui/tabs/straightlining_tab.py — Straightlining analysis tab

Users drag columns from the left panel into:
  - Base variable (e.g. interviewer_id) — groups results
  - Question columns — the battery to check for repeated answers
"""

import streamlit as st
import pandas as pd
from ui.components.drag_drop import drop_zone, inject_drag_drop_js


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Detect respondents who gave the same answer across a battery of questions. "
        "Optionally group results by a base variable (e.g. interviewer ID) to see "
        "which interviewers have the most straightliners.</p>",
        unsafe_allow_html=True,
    )

    inject_drag_drop_js()

    # ── Configuration ─────────────────────────────────────────────────────────
    st.markdown("#### Configure")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(
            "<div style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
            "color:var(--ds-text2);margin-bottom:6px;'>Base variable "
            "<span style='font-weight:400;text-transform:none;'>(optional — e.g. interviewer_id)"
            "</span></div>",
            unsafe_allow_html=True,
        )
        base_col = drop_zone(
            "Base variable",
            key="sl_base_col",
            multi=False,
            help_text="Drag the grouping column here (e.g. interviewer_id). "
                      "If left empty, rows will be numbered automatically.",
        )
        base_col_val = base_col[0] if base_col else None

        # Validate
        if base_col_val and base_col_val not in df.columns:
            st.warning(f"Column '{base_col_val}' not found in data.")
            base_col_val = None

    with col_b:
        threshold = st.slider(
            "Same-answer threshold",
            min_value=0.5, max_value=1.0,
            value=st.session_state.rules_config.get("straightlining", {}).get("threshold", 0.9),
            step=0.05,
            help="Flag respondents where this % of answers in the battery are identical. "
                 "1.0 = 100% same answer.",
        )
        min_q = st.number_input(
            "Minimum questions required",
            min_value=2, max_value=50,
            value=st.session_state.rules_config.get("straightlining", {}).get("min_questions", 3),
            help="Only evaluate respondents who answered at least this many questions.",
        )

    st.markdown("#### Question columns to check")
    q_cols = drop_zone(
        "Question columns",
        key="sl_q_cols",
        multi=True,
        help_text="Drag the question columns here, or type as: Q1, Q2, Q3, Q4, Q5",
    )
    q_cols = [c for c in q_cols if c in df.columns]

    if not q_cols:
        st.info("Drag question columns here (or type them above) to run the check.")

    # Update config in session
    st.session_state.rules_config["straightlining"] = {
        "enabled": bool(q_cols),
        "question_columns": q_cols,
        "base_column": base_col_val,
        "interviewer_column": base_col_val,   # used by the existing check
        "threshold": threshold,
        "min_questions": int(min_q),
    }

    if q_cols:
        st.caption(
            f"Checking {len(q_cols)} column(s): {', '.join(q_cols[:8])}"
            f"{'…' if len(q_cols) > 8 else ''}"
        )
        if st.button("▶ Run straightlining check", type="primary"):
            from core.cleaner import DataCleaner
            from checks.advanced_checks import StraightliningCheck

            with st.spinner("Running..."):
                cfg = st.session_state.rules_config["straightlining"]

                # Add row number as default base if none selected
                df_work = df.copy()
                if not base_col_val:
                    df_work["_row_number"] = range(1, len(df_work) + 1)
                    effective_base = "_row_number"
                else:
                    effective_base = base_col_val

                check = StraightliningCheck(
                    question_columns=q_cols,
                    threshold=threshold,
                    interviewer_column=effective_base,
                    min_questions=int(min_q),
                )
                result = check.run(df_work)
                st.session_state["_sl_result"] = result

    # ── Results ───────────────────────────────────────────────────────────────
    sl_result = st.session_state.get("_sl_result")

    # Also check cached results from full QC run
    if sl_result is None:
        cached = next((r for r in results if r.check_name == "straightlining_check"), None)
        if cached:
            sl_result = cached

    if sl_result is None:
        return

    st.divider()
    meta = sl_result.metadata

    c1, c2, c3 = st.columns(3)
    c1.metric("Flagged respondents", meta.get("flagged_respondents", sl_result.flag_count))
    c2.metric("% of total",          f"{meta.get('pct_of_total', 0)}%")
    c3.metric("Threshold used",       f"{int(meta.get('threshold', threshold) * 100)}%")

    if sl_result.flag_count == 0:
        st.success("No straightliners detected with the current settings.")
        return

    # Flagged rows table
    st.markdown("#### Flagged respondents")
    show = [c for c in sl_result.flagged_rows.columns if not c.startswith("_")]
    score_cols = ["_sl_score", "_sl_modal_answer"]
    extra_show = show + [c for c in score_cols if c in sl_result.flagged_rows.columns]
    st.dataframe(sl_result.flagged_rows[extra_show], use_container_width=True, hide_index=True)

    # Interviewer / base variable summary
    if "interviewer_summary" in meta and meta["interviewer_summary"]:
        st.markdown(
            f"#### By {'base variable' if not base_col_val else base_col_val}"
        )
        int_df = pd.DataFrame(meta["interviewer_summary"])
        st.dataframe(int_df, use_container_width=True, hide_index=True)

        # Bar chart
        count_col = "sl_count" if "sl_count" in int_df.columns else int_df.columns[1]
        id_col    = int_df.columns[0]
        chart_df  = int_df.set_index(id_col)[count_col].sort_values(ascending=False).head(20)
        st.bar_chart(chart_df, height=220)
