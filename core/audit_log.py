"""
core/audit_log.py — Session audit trail

Records every QC pipeline run with timestamp, filename, config snapshot,
and flag counts. If a client asks "how did you QC this data?" you can
show them a timestamped log rather than trying to remember.

Usage:
    from core.audit_log import log_run, get_log_df, clear_log
    log_run(filename, results, config)
"""

from datetime import datetime
import pandas as pd


def log_run(filename: str, results: list, config: dict):
    """Append a pipeline run entry to the session-state audit log."""
    import streamlit as st

    if "audit_log" not in st.session_state:
        st.session_state.audit_log = []

    # Compact config snapshot — skip verbose rule lists
    config_snapshot = {
        k: v for k, v in config.items()
        if k not in ("pattern_rules", "range_rules", "logic_rules")
    }

    entry = {
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename":       filename,
        "rows":           None,   # filled in by run_pipeline
        "checks_run":     len(results),
        "total_flags":    sum(r.flag_count for r in results),
        "critical_flags": sum(r.flag_count for r in results if r.severity == "critical"),
        "warning_flags":  sum(r.flag_count for r in results if r.severity == "warning"),
        "info_flags":     sum(r.flag_count for r in results if r.severity == "info"),
        "checks": [
            {"check": r.check_name, "flags": r.flag_count, "severity": r.severity}
            for r in results
        ],
        "config": config_snapshot,
    }
    # Most recent first
    st.session_state.audit_log.insert(0, entry)


def set_last_row_count(n_rows: int):
    """Set the row count on the most recent log entry (called after df is known)."""
    import streamlit as st
    if st.session_state.get("audit_log"):
        st.session_state.audit_log[0]["rows"] = n_rows


def get_log_df() -> pd.DataFrame:
    """Return the audit log as a flat DataFrame (one row per pipeline run)."""
    import streamlit as st
    log = st.session_state.get("audit_log", [])
    if not log:
        return pd.DataFrame()
    rows = []
    for entry in log:
        rows.append({
            "Timestamp":      entry["timestamp"],
            "File":           entry["filename"],
            "Rows":           entry.get("rows", "—"),
            "Checks Run":     entry["checks_run"],
            "Total Flags":    entry["total_flags"],
            "Critical Flags": entry["critical_flags"],
            "Warning Flags":  entry["warning_flags"],
            "Info Flags":     entry["info_flags"],
        })
    return pd.DataFrame(rows)


def get_log_detail(index: int = 0) -> dict:
    """Return the full detail dict for a specific log entry."""
    import streamlit as st
    log = st.session_state.get("audit_log", [])
    if not log or index >= len(log):
        return {}
    return log[index]


def clear_log():
    """Clear the audit log from session state."""
    import streamlit as st
    st.session_state.audit_log = []
