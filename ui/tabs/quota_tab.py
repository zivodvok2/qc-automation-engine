"""
ui/tabs/quota_tab.py — Quota Monitoring

Given a target sample composition (e.g. 50% female, 30% aged 18–34),
shows achieved vs target in real time and alerts when a quota cell
is overfilled or at risk of being missed.
"""

import streamlit as st
import pandas as pd


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Define your target sample quotas and track achieved counts in real time. "
        "Alerts when a cell is overfilled or running short.</p>",
        unsafe_allow_html=True,
    )

    if "quota_targets" not in st.session_state:
        st.session_state.quota_targets = []

    # ── Add quota cell ────────────────────────────────────────────────────────
    with st.expander("➕ Add quota cell", expanded=not st.session_state.quota_targets):
        cols = df.columns.tolist()

        c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
        q_col  = c1.selectbox("Column",   [""] + cols, key="qt_col")
        q_val  = c2.text_input("Value",   placeholder="e.g. Female", key="qt_val")
        q_type = c3.radio("Target type", ["Count", "Percent"], horizontal=True, key="qt_type")
        q_tgt  = c4.number_input(
            "Target",
            min_value=0.0,
            max_value=100.0 if q_type == "Percent" else float(len(df) * 10),
            value=50.0 if q_type == "Percent" else 100.0,
            key="qt_tgt",
        )

        if st.button("Add quota cell", type="primary"):
            if q_col and q_val:
                st.session_state.quota_targets.append({
                    "column": q_col,
                    "value": q_val,
                    "target_type": q_type,
                    "target": q_tgt,
                    "label": f"{q_col} = {q_val}",
                })
                st.rerun()
            else:
                st.warning("Select a column and enter a value.")

    if not st.session_state.quota_targets:
        st.info("No quota cells defined yet. Use the form above to add your first target.")
        return

    # ── Compute achieved counts ───────────────────────────────────────────────
    total_n = len(df)
    rows = []
    for cell in st.session_state.quota_targets:
        col = cell["column"]
        val = cell["value"]
        tgt = cell["target"]

        if col not in df.columns:
            achieved_n = 0
        else:
            achieved_n = int((df[col].astype(str).str.strip() == str(val).strip()).sum())

        achieved_pct = (achieved_n / total_n * 100) if total_n else 0.0

        if cell["target_type"] == "Percent":
            target_n   = round(tgt / 100 * total_n)
            target_pct = tgt
        else:
            target_n   = int(tgt)
            target_pct = (target_n / total_n * 100) if total_n else 0.0

        gap         = achieved_n - target_n
        pct_of_tgt  = (achieved_n / target_n * 100) if target_n else 0.0

        rows.append({
            "cell":         cell,
            "achieved_n":   achieved_n,
            "achieved_pct": achieved_pct,
            "target_n":     target_n,
            "target_pct":   target_pct,
            "gap":          gap,
            "pct_of_tgt":   pct_of_tgt,
        })

    # ── Headline metrics ──────────────────────────────────────────────────────
    overfilled  = sum(1 for r in rows if r["gap"] > 0)
    underfilled = sum(1 for r in rows if r["pct_of_tgt"] < 80)
    on_track    = len(rows) - overfilled - underfilled

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total respondents", f"{total_n:,}")
    m2.metric("Quota cells",       len(rows))
    m3.metric("Overfilled",        overfilled,  delta=None if overfilled == 0 else f"+{overfilled}")
    m4.metric("At risk (< 80%)",   underfilled)

    st.divider()

    # ── Quota grid ────────────────────────────────────────────────────────────
    st.markdown("#### Quota Progress")

    for i, row in enumerate(rows):
        cell        = row["cell"]
        achieved_n  = row["achieved_n"]
        target_n    = row["target_n"]
        pct_of_tgt  = row["pct_of_tgt"]
        gap         = row["gap"]

        # RAG colour
        if pct_of_tgt > 100:
            badge   = "🔴 OVERFILLED"
            bg      = "var(--ds-error, #dc3545)"
        elif pct_of_tgt >= 80:
            badge   = "🟢 ON TRACK"
            bg      = "var(--ds-success, #198754)"
        elif pct_of_tgt >= 50:
            badge   = "🟡 AT RISK"
            bg      = "var(--ds-warning, #fd7e14)"
        else:
            badge   = "🔴 CRITICAL"
            bg      = "var(--ds-error, #dc3545)"

        gap_str = f"+{gap}" if gap > 0 else str(gap)

        col_a, col_b, col_del = st.columns([7, 1, 1])
        with col_a:
            st.markdown(
                f"<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
                f"border-radius:8px;padding:14px 18px;margin-bottom:8px;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"margin-bottom:8px;'>"
                f"<span style='font-family:var(--ds-head);font-weight:700;font-size:13px;'>"
                f"{cell['label']}</span>"
                f"<span style='font-size:11px;padding:2px 8px;border-radius:10px;"
                f"background:{bg};color:#fff;'>{badge}</span>"
                f"</div>"
                f"<div style='font-size:12px;color:var(--ds-text2);'>"
                f"Achieved: <b style='color:var(--ds-text);'>{achieved_n:,}</b> / "
                f"Target: <b style='color:var(--ds-text);'>{target_n:,}</b> &nbsp;·&nbsp; "
                f"Gap: <b style='color:var(--ds-text);'>{gap_str}</b> &nbsp;·&nbsp; "
                f"{pct_of_tgt:.1f}% of target</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            progress_val = min(pct_of_tgt / 100, 1.0)
            st.progress(progress_val)
        with col_del:
            if st.button("✕", key=f"del_qt_{i}", help="Remove this quota cell"):
                st.session_state.quota_targets.pop(i)
                st.rerun()

    # ── Alert summary ─────────────────────────────────────────────────────────
    st.divider()
    alerts = [r for r in rows if r["gap"] > 0 or r["pct_of_tgt"] < 80]
    if alerts:
        st.markdown("#### Alerts")
        for r in alerts:
            cell = r["cell"]
            if r["gap"] > 0:
                st.error(
                    f"**{cell['label']}** is overfilled by {r['gap']:,} respondents "
                    f"({r['pct_of_tgt']:.1f}% of target). Stop collecting this group."
                )
            elif r["pct_of_tgt"] < 80:
                remaining = r["target_n"] - r["achieved_n"]
                st.warning(
                    f"**{cell['label']}** is at {r['pct_of_tgt']:.1f}% of target. "
                    f"Need {remaining:,} more to hit target."
                )
    else:
        st.success("All quota cells are on track.")

    # ── Export ────────────────────────────────────────────────────────────────
    import io
    export_rows = []
    for r in rows:
        export_rows.append({
            "Cell":         r["cell"]["label"],
            "Column":       r["cell"]["column"],
            "Value":        r["cell"]["value"],
            "Target":       r["target_n"],
            "Achieved":     r["achieved_n"],
            "Gap":          r["gap"],
            "% of Target":  round(r["pct_of_tgt"], 1),
            "Status":       "OVERFILLED" if r["gap"] > 0 else ("ON TRACK" if r["pct_of_tgt"] >= 80 else "AT RISK"),
        })
    export_df = pd.DataFrame(export_rows)
    buf = io.BytesIO(export_df.to_csv(index=False).encode())
    st.download_button(
        "↓ Export quota report (CSV)",
        data=buf,
        file_name="quota_monitoring.csv",
        mime="text/csv",
    )
