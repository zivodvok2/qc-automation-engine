"""
ui/tabs/logic_tab.py — Logic Checks tab

Provides an interactive rule builder where users can:
- Drag columns from the panel into IF/THEN condition fields
- Type column names as comma-separated values
- Define multi-condition rules with rich operators
- See violations immediately after running
"""

import streamlit as st
import pandas as pd
from ui.components.drag_drop import drop_zone, inject_drag_drop_js

OPERATORS = [">", "<", ">=", "<=", "==", "!=", "is_null", "not_null",
             "is_numeric", "is_string", "in_list", "not_in_list"]

OPERATOR_HELP = {
    ">": "Greater than",  "<": "Less than",
    ">=": "Greater or equal", "<=": "Less or equal",
    "==": "Equals", "!=": "Not equals",
    "is_null": "Is empty / missing", "not_null": "Is not empty",
    "is_numeric": "Is a number", "is_string": "Is text",
    "in_list": "Value is in list (comma-sep)", "not_in_list": "Value not in list",
}


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Build conditional rules: <em>if column A meets a condition, "
        "column B must meet another condition.</em> "
        "Drag columns from the left panel, or type names directly.</p>",
        unsafe_allow_html=True,
    )

    inject_drag_drop_js()

    # ── Rule builder ─────────────────────────────────────────────────────────
    with st.expander("➕ Add new logic rule", expanded=True):
        rule_desc = st.text_input(
            "Rule description",
            placeholder="e.g. Respondents under 18 should not be married",
            key="lc_desc",
        )

        st.markdown(
            "<div style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
            "color:var(--ds-text2);margin:12px 0 4px;'>IF conditions "
            "<span style='font-weight:400;text-transform:none;'>(all must be true)</span></div>",
            unsafe_allow_html=True,
        )

        ic1, ic2, ic3 = st.columns([3, 2, 2])
        with ic1:
            if_col = drop_zone("IF column", "lc_if_col", multi=False,
                               help_text="Drag a column here or type its name")
        with ic2:
            if_op = st.selectbox(
                "Operator",
                OPERATORS,
                key="lc_if_op",
                format_func=lambda x: f"{x}  — {OPERATOR_HELP.get(x, '')}",
                label_visibility="collapsed",
            )
        with ic3:
            if_val = st.text_input(
                "Value", key="lc_if_val",
                placeholder="e.g. 18  or  Yes, No",
                label_visibility="collapsed",
            )

        st.markdown(
            "<div style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
            "color:var(--ds-text2);margin:12px 0 4px;'>THEN conditions "
            "<span style='font-weight:400;text-transform:none;'>(add multiple to check "
            "several columns at once)</span></div>",
            unsafe_allow_html=True,
        )

        tc1, tc2, tc3 = st.columns([3, 2, 2])
        with tc1:
            then_col = drop_zone("THEN column(s)", "lc_then_col", multi=True,
                                 help_text="Drag one or more columns here")
        with tc2:
            then_op = st.selectbox(
                "Then operator",
                OPERATORS,
                key="lc_then_op",
                format_func=lambda x: f"{x}  — {OPERATOR_HELP.get(x, '')}",
                label_visibility="collapsed",
            )
        with tc3:
            then_val = st.text_input(
                "Then value", key="lc_then_val",
                placeholder="optional",
                label_visibility="collapsed",
            )

        if st.button("✚ Add Rule", type="primary", use_container_width=False):
            if_col_list   = [c.strip() for c in ",".join(if_col).split(",") if c.strip()]
            then_col_list = [c.strip() for c in ",".join(then_col).split(",") if c.strip()]

            if if_col_list and then_col_list:
                # Build multi-column THEN conditions
                then_conditions = [
                    {"column": tc, "operator": then_op,
                     "value": then_val.strip() or None}
                    for tc in then_col_list
                ]
                rule = {
                    "description": rule_desc or
                        f"If {', '.join(if_col_list)} {if_op} → {', '.join(then_col_list)} {then_op}",
                    "if_conditions": [
                        {"column": ic, "operator": if_op,
                         "value": if_val.strip() or None}
                        for ic in if_col_list
                    ],
                    "then_conditions": then_conditions,
                }
                st.session_state.custom_logic_rules.append(rule)
                st.success(f"Rule added: {rule['description']}")
                st.rerun()
            else:
                st.warning("Please specify at least one IF column and one THEN column.")

    # ── Existing rules list ───────────────────────────────────────────────────
    if st.session_state.custom_logic_rules:
        st.markdown("#### Active logic rules")
        for i, rule in enumerate(st.session_state.custom_logic_rules):
            col_desc, col_del = st.columns([6, 1])
            with col_desc:
                if_summary   = " AND ".join(
                    f"{c['column']} {c['operator']} {c.get('value','')}"
                    for c in rule.get("if_conditions", [])
                )
                then_summary = " · ".join(
                    f"{c['column']} {c['operator']} {c.get('value','')}"
                    for c in rule.get("then_conditions", [])
                )
                st.markdown(
                    f"<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
                    f"border-left:3px solid var(--ds-accent);border-radius:6px;padding:10px 14px;"
                    f"margin-bottom:6px;'>"
                    f"<div style='font-size:12px;font-weight:500;color:var(--ds-text);margin-bottom:4px;'>"
                    f"{rule.get('description','')}</div>"
                    f"<div style='font-size:11px;color:var(--ds-text2);'>"
                    f"<span style='color:var(--ds-info);'>IF</span> {if_summary} &nbsp;→&nbsp; "
                    f"<span style='color:var(--ds-warning);'>THEN</span> {then_summary}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("✕", key=f"del_lr_{i}"):
                    st.session_state.custom_logic_rules.pop(i)
                    st.rerun()
    else:
        st.info("No logic rules added yet. Use the builder above to create your first rule.")

    # ── Results ───────────────────────────────────────────────────────────────
    logic_results = [r for r in results if r.check_name == "logic_check"]
    if logic_results:
        r = logic_results[0]
        st.divider()
        st.markdown(f"#### Results — {r.flag_count:,} violations found")
        if r.flag_count > 0:
            show = [c for c in r.flagged_rows.columns if not c.startswith("_")]
            # Group by rule
            if "_logic_rule" in r.flagged_rows.columns:
                for rule_name, group in r.flagged_rows.groupby("_logic_rule"):
                    with st.expander(f"{rule_name} — {len(group)} violations"):
                        st.dataframe(group[show].head(100),
                                     use_container_width=True, hide_index=True)
            else:
                st.dataframe(r.flagged_rows[show].head(100),
                             use_container_width=True, hide_index=True)
        else:
            st.success("No violations found for the current rules.")
    elif st.session_state.custom_logic_rules:
        st.info("Rules are set. Click **↺ Rerun QC** in the sidebar to check them.")
