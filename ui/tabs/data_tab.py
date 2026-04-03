"""
ui/tabs/data_tab.py — Data Preview tab
"""

import streamlit as st
import pandas as pd


def render(df: pd.DataFrame):
    st.markdown("#### Data Preview")

    c1, c2 = st.columns([3, 2])
    with c1:
        search = st.text_input("Filter rows", placeholder="Type to search any value...")
    with c2:
        col_filter = st.multiselect(
            "Show columns", options=df.columns.tolist(),
            default=df.columns.tolist(), key="data_cols"
        )

    disp = df[col_filter] if col_filter else df
    if search:
        mask = disp.apply(
            lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1
        )
        disp = disp[mask]

    st.caption(f"Showing {len(disp):,} of {len(df):,} rows · {len(disp.columns)} columns")
    st.dataframe(disp, use_container_width=True, height=520)
