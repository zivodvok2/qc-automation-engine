"""
ui/tabs/logic_tab.py — Logic Checks tab with column_selector_widget
"""

import streamlit as st
import pandas as pd
from ui.components.drag_drop import column_selector_widget

OPERATORS = [">","<",">=","<=","==","!=","is_null","not_null",
             "is_numeric","is_string","in_list","not_in_list"]
OP_LABELS  = {
    ">": "> greater than",  "<": "< less than",
    ">=": ">= greater or equal", "<=": "<= less or equal",
    "==": "== equals", "!=": "!= not equals",
    "is_null": "is_null (empty)", "not_null": "not_null (has value)",
    "is_numeric": "is_numeric", "is_string": "is_string",
    "in_list": "in_list (value in list)", "not_in_list": "not_in_list",
}


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Define conditional rules: <em>if a column meets a condition, "
        "one or more other columns must meet conditions too.</em><br>"
        "Click columns to select them, or describe rules in plain English using AI.</p>",
        unsafe_allow_html=True,
    )

    # ── Natural-language rule builder (Groq) ──────────────────────────────────
    from core.groq_utils import groq_available, groq_json

    with st.expander("🤖 Describe rule in plain English (AI)", expanded=False):
        if not groq_available():
            st.warning("Set GROQ_API_KEY in your .env file to enable AI rule building.")
        else:
            nl_input = st.text_area(
                "Describe the rule",
                placeholder=(
                    "e.g. If age is under 18 then marital status should be empty\n"
                    "e.g. If consent is No then Q1 through Q10 should all be empty\n"
                    "e.g. If gender is Male then pregnancy question should be empty"
                ),
                key="lc_nl_input",
                height=80,
            )
            if st.button("🤖 Convert to rule", key="lc_nl_btn", type="primary"):
                if nl_input.strip():
                    with st.spinner("Parsing with AI…"):
                        try:
                            col_sample = ", ".join(df.columns[:40].tolist())
                            parsed = groq_json(
                                prompt=(
                                    f"Convert this survey skip-logic rule to JSON.\n\n"
                                    f"Rule: {nl_input}\n\n"
                                    f"Available columns (sample): {col_sample}\n\n"
                                    "Return ONLY a JSON object:\n"
                                    '{"description": "...", "if_conditions": [{"column": "...", "operator": "...", "value": "..."}], '
                                    '"then_conditions": [{"column": "...", "operator": "...", "value": null}]}\n\n'
                                    "Operators: >, <, >=, <=, ==, !=, is_null, not_null, in_list, not_in_list\n"
                                    "For 'should be empty' use operator is_null with value null.\n"
                                    "Return ONLY the JSON, no explanation."
                                ),
                                system="You are a survey logic rule parser. Return only valid JSON.",
                            )
                            if isinstance(parsed, dict) and "if_conditions" in parsed:
                                st.session_state.custom_logic_rules.append(parsed)
                                st.success(f"Rule added: {parsed.get('description', '')}")
                                st.rerun()
                            else:
                                st.error("Could not parse the rule — try rephrasing.")
                        except Exception as e:
                            st.error(f"AI error: {e}")
                else:
                    st.warning("Enter a description first.")

    with st.expander("➕ Add new rule manually", expanded=True):
        rule_desc = st.text_input("Description",
                                  placeholder="e.g. Respondents under 18 should not be married",
                                  key="lc_desc")

        st.markdown("**IF** — select the trigger column")
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            if_sel = column_selector_widget(
                "IF column", df.columns.tolist(), key="lc_if", multi=False
            )
            if_col_val = if_sel[0] if if_sel else ""
        with c2:
            if_op = st.selectbox("Operator", OPERATORS, key="lc_if_op",
                                 format_func=lambda x: OP_LABELS.get(x, x),
                                 label_visibility="collapsed")
        with c3:
            if_val = st.text_input("Value", key="lc_if_val",
                                   placeholder="e.g. 18 or Yes",
                                   label_visibility="collapsed")

        st.markdown("**THEN** — select column(s) that must meet a condition")
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            then_sel = column_selector_widget(
                "THEN column(s)", df.columns.tolist(), key="lc_then", multi=True
            )
            then_cols = [c for c in then_sel if c]
        with c2:
            then_op = st.selectbox("Then operator", OPERATORS, key="lc_then_op",
                                   format_func=lambda x: OP_LABELS.get(x, x),
                                   label_visibility="collapsed")
        with c3:
            then_val = st.text_input("Then value", key="lc_then_val",
                                     placeholder="optional",
                                     label_visibility="collapsed")

        if st.button("✚ Add Rule", type="primary"):
            if if_col_val and then_cols:
                rule = {
                    "description": rule_desc or f"If {if_col_val} {if_op} → {', '.join(then_cols)} {then_op}",
                    "if_conditions":   [{"column": if_col_val, "operator": if_op,
                                         "value": if_val.strip() or None}],
                    "then_conditions": [{"column": tc, "operator": then_op,
                                         "value": then_val.strip() or None}
                                        for tc in then_cols],
                }
                st.session_state.custom_logic_rules.append(rule)
                st.success(f"Rule added: {rule['description']}")
                st.rerun()
            else:
                st.warning("Please select at least one IF column and one THEN column.")

    # Active rules
    if st.session_state.custom_logic_rules:
        st.markdown("#### Active rules")
        for i, rule in enumerate(st.session_state.custom_logic_rules):
            cc, cd = st.columns([6, 1])
            if_s   = " AND ".join(f"{c['column']} {c['operator']} {c.get('value','')}"
                                   for c in rule.get("if_conditions", []))
            then_s = " · ".join(f"{c['column']} {c['operator']} {c.get('value','')}"
                                 for c in rule.get("then_conditions", []))
            cc.markdown(
                f"<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
                f"border-left:3px solid var(--ds-accent);border-radius:6px;"
                f"padding:10px 14px;margin-bottom:6px;'>"
                f"<b style='font-size:12px;'>{rule.get('description','')}</b><br>"
                f"<span style='font-size:11px;color:var(--ds-text2);'>"
                f"<span style='color:var(--ds-info);'>IF</span> {if_s} &nbsp;→&nbsp; "
                f"<span style='color:var(--ds-warning);'>THEN</span> {then_s}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if cd.button("✕", key=f"dlr_{i}"):
                st.session_state.custom_logic_rules.pop(i); st.rerun()
    else:
        st.info("No logic rules yet. Use the builder above to add your first rule.")

    # Results
    logic_r = [r for r in results if r.check_name == "logic_check"]
    if logic_r:
        r = logic_r[0]
        st.divider()
        st.markdown(f"#### Results — {r.flag_count:,} violations")
        if r.flag_count > 0:
            show = [c for c in r.flagged_rows.columns if not c.startswith("_")]
            if "_logic_rule" in r.flagged_rows.columns:
                for rule_name, grp in r.flagged_rows.groupby("_logic_rule"):
                    with st.expander(f"{rule_name} — {len(grp)} violations"):
                        st.dataframe(grp[show].head(100), use_container_width=True, hide_index=True)
            else:
                st.dataframe(r.flagged_rows[show].head(100), use_container_width=True, hide_index=True)
        else:
            st.success("No violations found.")
    elif st.session_state.custom_logic_rules:
        st.info("Rules are set. Click **↺ Rerun QC** in the sidebar to check them.")
