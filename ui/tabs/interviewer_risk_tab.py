"""
ui/tabs/interviewer_risk_tab.py — Interviewer Risk Scoring

Combines flags from all checks into a single weighted risk score (0–100)
per interviewer, with RAG (Red / Amber / Green) status and a ranked table.
One screen — no mental joins across tabs.

Check weights (sum to 100):
  Fabrication            35  — hardest to explain innocently
  Consent violations     25  — critical, data integrity
  Duration anomaly       20  — strong signal
  Straightlining         15  — moderate signal
  Productivity outlier    5  — weak alone, but adds up
"""

import streamlit as st
import pandas as pd

_WEIGHTS = {
    "fabrication_check":              35,
    "consent_eligibility_check":      25,
    "interviewer_duration_check":     20,
    "straightlining_check":           15,
    "interviewer_productivity_check":  5,
}

_LABELS = {
    "fabrication_check":              "Fabrication",
    "consent_eligibility_check":      "Consent Violations",
    "interviewer_duration_check":     "Duration Anomaly",
    "straightlining_check":           "Straightlining",
    "interviewer_productivity_check": "Productivity",
}

_DESCS = {
    "fabrication_check":              "Sequential IDs or low-variance numeric patterns",
    "consent_eligibility_check":      "Disqualified respondents with subsequent data",
    "interviewer_duration_check":     "Mean duration outside peer IQR bounds",
    "straightlining_check":           "Respondents giving identical answers across question battery",
    "interviewer_productivity_check": "Interview count outside peer IQR bounds",
}


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Combines all QC flags into a single weighted risk score per interviewer (0–100). "
        "One screen — no mental joins across tabs.</p>",
        unsafe_allow_html=True,
    )

    # ── Configuration row ─────────────────────────────────────────────────────
    cfg = st.session_state.get("rules_config", {})
    detected = (
        cfg.get("interviewer_duration_check",     {}).get("interviewer_column") or
        cfg.get("interviewer_productivity_check", {}).get("interviewer_column") or
        cfg.get("fabrication_check",              {}).get("interviewer_column") or ""
    )

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        int_col = st.text_input(
            "Interviewer column",
            value=detected,
            key="risk_int_col",
            help="Column in the dataset that identifies each interviewer",
        )
    with c2:
        flag_thr = st.number_input(
            "Flag % alert threshold",
            value=10, min_value=1, max_value=100,
            key="risk_flag_thr",
            help="Interviewers above this flag rate trigger an alert",
        )
    with c3:
        red_thr = st.number_input(
            "Red score ≥",
            value=60, min_value=2, max_value=100,
            key="risk_red_thr",
            help="Risk score at or above this = High Risk (red)",
        )
    with c4:
        amber_thr = st.number_input(
            "Amber score ≥",
            value=30, min_value=1, max_value=99,
            key="risk_amber_thr",
            help="Risk score at or above this = Medium Risk (amber)",
        )

    if not int_col:
        st.info("Enter the interviewer column name above to generate the risk table.")
        return
    if int_col not in df.columns:
        st.warning(f"Column '{int_col}' not found in dataset. Available columns: {', '.join(df.columns[:10])}…")
        return

    # ── Build risk table ──────────────────────────────────────────────────────
    risk_df = _build_risk_table(df, results, int_col, int(red_thr), int(amber_thr))

    if risk_df.empty:
        st.info(
            "No interviewer-level flags found. Make sure at least one check "
            "(duration, productivity, fabrication, straightlining, or consent) "
            "is enabled and flags at least one row."
        )
        return

    # ── Headline metrics ──────────────────────────────────────────────────────
    red_n   = (risk_df["Risk"] == "🔴 HIGH").sum()
    amb_n   = (risk_df["Risk"] == "🟡 MED").sum()
    grn_n   = (risk_df["Risk"] == "🟢 LOW").sum()
    above_n = (risk_df["Flag Rate %"] > flag_thr).sum()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Interviewers",               len(risk_df))
    m2.metric("🔴 High Risk",               red_n)
    m3.metric("🟡 Medium Risk",             amb_n)
    m4.metric("🟢 Low Risk",                grn_n)
    m5.metric(f"Above {flag_thr}% flag rate", above_n)

    st.divider()

    # ── Ranked table ──────────────────────────────────────────────────────────
    st.markdown("#### Interviewer Risk Rankings")
    st.caption("Sorted by Risk Score (highest = investigate first). Click a column header to re-sort.")

    display = risk_df.sort_values("Risk Score", ascending=False).reset_index(drop=True)
    display.index = display.index + 1  # 1-based rank

    col_config = {
        "Risk Score": st.column_config.ProgressColumn(
            "Risk Score",
            help="Weighted composite score (0–100). Higher = more flags across more checks.",
            min_value=0,
            max_value=100,
            format="%d",
        ),
        "Flag Rate %": st.column_config.NumberColumn(
            "Flag Rate %",
            help="% of this interviewer's rows flagged (deduplicated across all checks)",
            format="%.1f%%",
        ),
        "Risk": st.column_config.TextColumn("Risk", width="small"),
        "Total Interviews": st.column_config.NumberColumn("Total Interviews"),
    }

    st.dataframe(display, use_container_width=True, column_config=col_config)

    # ── Download risk table ───────────────────────────────────────────────────
    import io
    risk_csv = io.BytesIO()
    display.to_csv(risk_csv, index_label="Rank")
    risk_csv.seek(0)
    st.download_button(
        "↓ Export risk table (CSV)",
        data=risk_csv,
        file_name="interviewer_risk_scores.csv",
        mime="text/csv",
        use_container_width=False,
    )

    # ── Flag rate alerts ──────────────────────────────────────────────────────
    st.divider()
    st.markdown(f"#### Flag Rate Alerts  ·  threshold: {flag_thr}%")

    above_rows = risk_df[risk_df["Flag Rate %"] > flag_thr].sort_values("Risk Score", ascending=False)
    if above_rows.empty:
        st.success(f"No interviewers exceed the {flag_thr}% flag rate threshold.")
    else:
        for _, row in above_rows.iterrows():
            st.warning(
                f"**{row[int_col]}**: {row['Flag Rate %']:.1f}% of interviews flagged "
                f"(above {flag_thr}% threshold) · Risk Score: **{int(row['Risk Score'])}** · {row['Risk']}"
            )

    # ── Feedback letter generator ─────────────────────────────────────────────
    st.divider()
    st.markdown("#### Feedback Letter Generator")
    st.caption("Generate a structured feedback letter for a flagged interviewer, ready to send.")

    from core.groq_utils import groq_available, groq_chat

    if not groq_available():
        st.info("Set GROQ_API_KEY in your .env file to enable AI-generated feedback letters.")
    else:
        interviewer_ids = risk_df[int_col].tolist()
        sel_int = st.selectbox(
            "Select interviewer",
            interviewer_ids,
            key="risk_letter_int",
            format_func=lambda x: f"{x}  ({risk_df.loc[risk_df[int_col]==x, 'Risk'].values[0]}  ·  score {int(risk_df.loc[risk_df[int_col]==x, 'Risk Score'].values[0])})",
        )

        if st.button("✉ Generate feedback letter", type="primary", key="risk_letter_btn"):
            int_row = risk_df[risk_df[int_col] == sel_int].iloc[0]
            flag_detail = []
            for check_name, label in _LABELS.items():
                col_label = label + " Flags"
                if col_label in int_row and int(int_row[col_label]) > 0:
                    flag_detail.append(f"- {label}: {int(int_row[col_label])} flagged interviews")

            flag_summary = "\n".join(flag_detail) if flag_detail else "- Multiple QC flags across checks"

            with st.spinner("Drafting letter…"):
                try:
                    letter = groq_chat(
                        prompt=(
                            f"Write a professional but firm field supervisor feedback letter "
                            f"for an interviewer with the following QC issues.\n\n"
                            f"Interviewer ID: {sel_int}\n"
                            f"Risk Score: {int(int_row['Risk Score'])} / 100\n"
                            f"Risk Level: {int_row['Risk']}\n"
                            f"Total interviews: {int(int_row['Total Interviews'])}\n"
                            f"Flag rate: {int_row['Flag Rate %']:.1f}%\n\n"
                            f"Specific issues found:\n{flag_summary}\n\n"
                            "The letter should:\n"
                            "1. Open professionally (Dear Interviewer ...)\n"
                            "2. Summarise the QC findings clearly\n"
                            "3. Explain what each issue means and why it matters\n"
                            "4. State specific corrective actions required\n"
                            "5. Set expectations for re-training or field supervision\n"
                            "6. Close with a positive note about data quality standards\n\n"
                            "Keep it under 400 words. Plain English, no jargon."
                        ),
                        system="You are a senior field research manager writing quality control feedback letters.",
                        temperature=0.4,
                        max_tokens=600,
                    )
                    st.session_state["_risk_letter_text"] = letter
                    st.session_state["_risk_letter_int"]  = sel_int
                except Exception as e:
                    st.error(f"Letter generation failed: {e}")

        if st.session_state.get("_risk_letter_text") and st.session_state.get("_risk_letter_int") == sel_int:
            st.markdown(
                f"<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
                f"border-radius:8px;padding:20px 24px;margin-top:12px;"
                f"font-family:var(--ds-mono);font-size:12px;line-height:1.8;white-space:pre-wrap;'>"
                f"{st.session_state['_risk_letter_text']}"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.download_button(
                f"↓ Download letter — {sel_int}",
                data=st.session_state["_risk_letter_text"],
                file_name=f"feedback_letter_{sel_int}.txt",
                mime="text/plain",
            )

    # ── Score methodology ─────────────────────────────────────────────────────
    with st.expander("Score methodology"):
        w_rows = [
            {
                "Check": _LABELS.get(k, k),
                "Weight (max pts)": v,
                "What it detects": _DESCS.get(k, ""),
                "Active": "✓" if any(r.check_name == k and r.flag_count > 0 for r in results) else "—",
            }
            for k, v in _WEIGHTS.items()
        ]
        st.dataframe(pd.DataFrame(w_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Each check contributes points proportional to that interviewer's flag rate "
            "for that check (flags ÷ total interviews × weight). "
            "Scores are summed and capped at 100. Only checks with flags contribute."
        )


def _build_risk_table(
    df: pd.DataFrame,
    results: list,
    int_col: str,
    red_thr: int,
    amber_thr: int,
) -> pd.DataFrame:
    """Aggregate QC results per interviewer and compute risk scores."""

    # Interviews per interviewer
    total_counts = df.groupby(int_col).size().rename("Total Interviews")
    risk = pd.DataFrame({"Total Interviews": total_counts})

    # Per-check flag counts per interviewer
    found_any = False
    for result in results:
        if result.flag_count == 0 or result.check_name not in _WEIGHTS:
            continue
        if int_col not in result.flagged_rows.columns:
            continue
        per_int = result.flagged_rows.groupby(int_col).size()
        risk[result.check_name] = risk.index.map(per_int).fillna(0)
        found_any = True

    if not found_any:
        return pd.DataFrame()

    # Weighted risk score
    risk["Risk Score"] = 0.0
    for check_name, weight in _WEIGHTS.items():
        if check_name in risk.columns:
            flag_rate = (risk[check_name] / risk["Total Interviews"]).clip(0, 1)
            risk["Risk Score"] += flag_rate * weight
    risk["Risk Score"] = risk["Risk Score"].clip(0, 100).round(1)

    # Deduplicated flag rate: unique row indices flagged across ALL checks
    all_flagged_idx: set = set()
    for result in results:
        if result.flag_count > 0:
            all_flagged_idx.update(result.flagged_rows.index.tolist())

    if all_flagged_idx:
        flagged_subset = df.loc[df.index.isin(all_flagged_idx)]
        if int_col in flagged_subset.columns:
            flagged_per_int = flagged_subset.groupby(int_col).size()
            risk["_unique_flagged"] = risk.index.map(flagged_per_int).fillna(0)
        else:
            risk["_unique_flagged"] = 0
    else:
        risk["_unique_flagged"] = 0

    risk["Flag Rate %"] = (
        risk["_unique_flagged"] / risk["Total Interviews"] * 100
    ).round(1)

    # RAG label
    risk["Risk"] = risk["Risk Score"].apply(
        lambda s: "🔴 HIGH" if s >= red_thr else ("🟡 MED" if s >= amber_thr else "🟢 LOW")
    )

    # Reset index so int_col becomes a data column
    risk = risk.reset_index()

    # Build readable flag-count columns
    display_cols = [int_col, "Total Interviews", "Flag Rate %", "Risk Score", "Risk"]
    for check_name in _WEIGHTS:
        if check_name in risk.columns:
            label = _LABELS.get(check_name, check_name) + " Flags"
            risk[label] = risk[check_name].astype(int)
            display_cols.append(label)

    return risk[[c for c in display_cols if c in risk.columns]]
