"""
ui/tabs/qc_tab.py — QC Report tab
"""

import streamlit as st
import pandas as pd
import io


def sev_emoji(s): return {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(s, "⚪")
def sev_color(s): return {"critical": "var(--ds-critical)", "warning": "var(--ds-warning)", "info": "var(--ds-info)"}.get(s, "var(--ds-text2)")


def render(df: pd.DataFrame, results: list):
    total_flags = sum(r.flag_count for r in results)
    crits = sum(1 for r in results if r.severity == "critical" and r.flag_count > 0)
    warns = sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0)
    infos = sum(1 for r in results if r.severity == "info"     and r.flag_count > 0)

    # Scorecards
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Checks run",   len(results))
    m2.metric("Total flags",  total_flags)
    m3.metric("🔴 Critical",  crits)
    m4.metric("🟡 Warnings",  warns)
    m5.metric("🔵 Info",      infos)

    st.divider()

    if total_flags == 0:
        st.success("✅ No issues detected — dataset passed all checks.")
    else:
        for sev, label in [("critical", "Critical Issues"), ("warning", "Warnings"), ("info", "Info")]:
            sev_res = [r for r in results if r.severity == sev and r.flag_count > 0]
            if not sev_res:
                continue
            st.markdown(
                f"<h4 style='color:{sev_color(sev)};margin-top:1rem;'>"
                f"{sev_emoji(sev)} {label}</h4>",
                unsafe_allow_html=True,
            )
            for r in sev_res:
                pct = r.flag_count / max(len(df), 1) * 100
                with st.expander(
                    f"{r.check_name} — **{r.flag_count:,}** rows ({pct:.1f}%)",
                    expanded=(sev == "critical"),
                ):
                    mc, dc = st.columns([2, 3])
                    with mc:
                        st.markdown("**Check metadata**")
                        st.json(r.summary(), expanded=False)
                    with dc:
                        if not r.flagged_rows.empty:
                            show = [c for c in r.flagged_rows.columns if not c.startswith("_")]
                            st.dataframe(
                                r.flagged_rows[show].head(50),
                                use_container_width=True,
                                hide_index=True,
                            )

    st.markdown("#### All checks summary")
    st.dataframe(
        pd.DataFrame([r.summary() for r in results]),
        use_container_width=True,
        hide_index=True,
    )
