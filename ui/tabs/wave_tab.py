"""
ui/tabs/wave_tab.py — Wave-over-Wave Comparison

Upload a second data file and compare QC flag rates, interviewer
performance, and missing data patterns between two waves.
Drift detection: interviewers clean in wave 1 but flagged in wave 2.
"""

import io
import streamlit as st
import pandas as pd

from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine


def _build_wave_cfg() -> dict:
    """Build config for wave 2 run using current session settings."""
    rc  = st.session_state.get("rules_config", {})
    cfg = dict(rc)
    cfg["logic_rules"] = (
        cfg.get("logic_rules", [])
        + st.session_state.get("custom_logic_rules", [])
    )
    cfg["consistency_rules"] = st.session_state.get("consistency_rules", [])
    return cfg


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Upload a second wave file to compare QC results, flag rates, and "
        "interviewer performance across waves. Detects interviewers who were "
        "clean in wave 1 but flagged in wave 2.</p>",
        unsafe_allow_html=True,
    )

    # ── Wave labels ───────────────────────────────────────────────────────────
    lc, rc_ = st.columns(2)
    w1_label = lc.text_input("Wave 1 label", value=st.session_state.get("filename", "Wave 1"), key="wave1_label")
    w2_label = rc_.text_input("Wave 2 label", value="Wave 2", key="wave2_label")

    # ── Wave 2 upload ─────────────────────────────────────────────────────────
    w2_file = st.file_uploader(
        "Upload Wave 2 file",
        type=["csv", "xlsx", "xls"],
        key="wave2_upload",
    )

    if w2_file is None:
        st.info("Upload a Wave 2 file to begin comparison.")
        return

    # Load + run pipeline on wave 2
    if st.session_state.get("_wave2_hash") != w2_file.name + str(w2_file.size):
        with st.spinner("Running QC on Wave 2…"):
            try:
                df2_raw   = DataLoader().load_from_buffer(w2_file)
                mappings  = st.session_state.get("column_mappings", {})
                if mappings:
                    df2_raw = df2_raw.rename(columns=mappings)
                df2       = DataCleaner().clean(df2_raw)
                cfg       = _build_wave_cfg()
                results2  = RuleEngine(config=cfg).run(df2)
                st.session_state["_wave2_df"]      = df2
                st.session_state["_wave2_results"] = results2
                st.session_state["_wave2_label"]   = w2_label
                st.session_state["_wave2_hash"]    = w2_file.name + str(w2_file.size)
            except Exception as e:
                st.error(f"Failed to load Wave 2: {e}")
                return
    else:
        df2      = st.session_state["_wave2_df"]
        results2 = st.session_state["_wave2_results"]

    results1 = results

    # ── Headline metrics ──────────────────────────────────────────────────────
    flags1 = sum(r.flag_count for r in results1)
    flags2 = sum(r.flag_count for r in results2)
    rate1  = flags1 / len(df)  * 100 if len(df)  else 0
    rate2  = flags2 / len(df2) * 100 if len(df2) else 0

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric(f"{w1_label} rows",       f"{len(df):,}")
    m2.metric(f"{w2_label} rows",       f"{len(df2):,}")
    m3.metric(f"{w1_label} flags",      f"{flags1:,}")
    m4.metric(f"{w2_label} flags",      f"{flags2:,}")
    m5.metric(f"{w1_label} flag rate",  f"{rate1:.1f}%")
    m6.metric(f"{w2_label} flag rate",  f"{rate2:.1f}%",
              delta=f"{rate2 - rate1:+.1f}%",
              delta_color="inverse")

    st.divider()

    # ── Check-by-check comparison ─────────────────────────────────────────────
    st.markdown("#### Flag Rate by Check")

    map1 = {r.check_name: r.flag_count for r in results1}
    map2 = {r.check_name: r.flag_count for r in results2}
    all_checks = sorted(set(map1) | set(map2))

    check_rows = []
    for chk in all_checks:
        n1    = map1.get(chk, 0)
        n2    = map2.get(chk, 0)
        r1    = n1 / len(df)  * 100 if len(df)  else 0
        r2    = n2 / len(df2) * 100 if len(df2) else 0
        delta = r2 - r1
        check_rows.append({
            "Check":                chk,
            f"{w1_label} flags":    n1,
            f"{w2_label} flags":    n2,
            f"{w1_label} rate %":   round(r1, 2),
            f"{w2_label} rate %":   round(r2, 2),
            "Delta (pp)":           round(delta, 2),
            "Direction":            "↑ worse" if delta > 1 else ("↓ better" if delta < -1 else "≈ stable"),
        })

    cmp_df = pd.DataFrame(check_rows)
    st.dataframe(
        cmp_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Delta (pp)": st.column_config.NumberColumn("Delta (pp)", format="%.2f"),
        },
    )

    # ── Interviewer drift ─────────────────────────────────────────────────────
    int_col = (
        st.session_state.get("rules_config", {})
        .get("interviewer_duration_check", {})
        .get("interviewer_column", "")
        or st.session_state.get("risk_int_col", "")
    )

    st.divider()
    st.markdown("#### Interviewer Drift")

    if not int_col:
        st.info("Set an interviewer column in the sidebar to enable drift detection.")
    elif int_col not in df.columns or int_col not in df2.columns:
        st.warning(f"Column '{int_col}' not found in one or both datasets.")
    else:
        drift_rows = _compute_drift(df, df2, results1, results2, int_col, w1_label, w2_label)
        if drift_rows.empty:
            st.success("No interviewers show significant flag-rate drift between waves.")
        else:
            st.dataframe(drift_rows, use_container_width=True, hide_index=True)

            # Highlight new problems
            new_problems = drift_rows[drift_rows["Drift"] == "🔴 NEW PROBLEM"]
            if not new_problems.empty:
                st.error(
                    f"**{len(new_problems)} interviewer(s) were clean in {w1_label} "
                    f"but flagged in {w2_label}.** Investigate immediately:\n\n"
                    + "\n".join(f"- **{r[int_col]}** ({r[f'{w2_label} flag rate %']:.1f}% flag rate)"
                                for _, r in new_problems.iterrows())
                )

    # ── Missing data comparison ───────────────────────────────────────────────
    st.divider()
    st.markdown("#### Missing Data — Wave Comparison")

    common_cols = sorted(set(df.columns) & set(df2.columns))
    if common_cols:
        miss_rows = []
        for col in common_cols:
            m1_ = df[col].isna().mean()  * 100
            m2_ = df2[col].isna().mean() * 100
            if max(m1_, m2_) >= 1:   # only show columns with meaningful missingness
                miss_rows.append({
                    "Column":            col,
                    f"{w1_label} miss%": round(m1_, 1),
                    f"{w2_label} miss%": round(m2_, 1),
                    "Delta":             round(m2_ - m1_, 1),
                })
        if miss_rows:
            miss_df = pd.DataFrame(miss_rows).sort_values("Delta", ascending=False, key=abs)
            st.dataframe(miss_df, use_container_width=True, hide_index=True)
        else:
            st.success("No columns with ≥1% missing in either wave.")
    else:
        st.warning("No columns in common between the two waves.")

    # ── Export ────────────────────────────────────────────────────────────────
    buf = io.BytesIO(cmp_df.to_csv(index=False).encode())
    st.download_button(
        "↓ Export wave comparison (CSV)",
        data=buf,
        file_name="wave_comparison.csv",
        mime="text/csv",
    )


def _compute_drift(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    results1: list,
    results2: list,
    int_col: str,
    label1: str,
    label2: str,
) -> pd.DataFrame:
    """Per-interviewer flag rates across two waves with drift classification."""

    def _flag_rate_per_interviewer(df, results, int_col):
        total = df.groupby(int_col).size().rename("total")
        all_flagged = set()
        for r in results:
            if r.flag_count > 0 and int_col in r.flagged_rows.columns:
                all_flagged.update(r.flagged_rows.index)
        if all_flagged:
            flagged_sub = df.loc[df.index.isin(all_flagged)]
            flagged_cnt = flagged_sub.groupby(int_col).size().rename("flagged")
        else:
            flagged_cnt = pd.Series(dtype=int, name="flagged")
        tbl = pd.DataFrame({"total": total}).join(flagged_cnt, how="left").fillna(0)
        tbl["rate"] = tbl["flagged"] / tbl["total"] * 100
        return tbl

    tbl1 = _flag_rate_per_interviewer(df1, results1, int_col)
    tbl2 = _flag_rate_per_interviewer(df2, results2, int_col)

    common = tbl1.index.intersection(tbl2.index)
    if common.empty:
        return pd.DataFrame()

    merged = pd.DataFrame({
        int_col:                  common,
        f"{label1} interviews":   tbl1.loc[common, "total"].values,
        f"{label2} interviews":   tbl2.loc[common, "total"].values,
        f"{label1} flag rate %":  tbl1.loc[common, "rate"].round(1).values,
        f"{label2} flag rate %":  tbl2.loc[common, "rate"].round(1).values,
    })
    merged["Delta (pp)"] = (
        merged[f"{label2} flag rate %"] - merged[f"{label1} flag rate %"]
    ).round(1)

    def _classify(row):
        r1 = row[f"{label1} flag rate %"]
        r2 = row[f"{label2} flag rate %"]
        if r1 < 5 and r2 >= 15:
            return "🔴 NEW PROBLEM"
        if row["Delta (pp)"] >= 10:
            return "🟡 WORSENING"
        if row["Delta (pp)"] <= -10:
            return "🟢 IMPROVING"
        return "≈ STABLE"

    merged["Drift"] = merged.apply(_classify, axis=1)
    return merged.sort_values("Delta (pp)", ascending=False).reset_index(drop=True)
