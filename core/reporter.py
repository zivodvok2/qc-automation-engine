"""
reporter.py - Generates flagged records CSV and QC summary CSV report
Updated: Removed openpyxl dependency to use standard CSV.
"""

import os
import pandas as pd
from typing import List
from core.validator import CheckResult
from core.utils import setup_logger, timestamp_str, ensure_output_dir

logger = setup_logger("reporter")


class Reporter:
    """
    Takes a list of CheckResults and produces:
    1. flagged_records.csv  - all flagged rows with issue metadata
    2. qc_summary.csv      - aggregated summary of all checks
    """

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = output_dir
        ensure_output_dir(output_dir)

    def generate(self, results: List[CheckResult], df_original: pd.DataFrame = None):
        """Main entry point. Generates all output files."""
        ts = timestamp_str()
        self._export_flagged_records(results, ts)
        self._export_qc_summary(results, df_original, ts)

    def _export_flagged_records(self, results: List[CheckResult], ts: str):
        """Combine all flagged rows into a single CSV with issue labels."""
        all_flagged = []

        for result in results:
            # Note: Changed result.flag_count to len(result.flagged_rows) for safety
            if len(result.flagged_rows) == 0:
                continue
            df = result.flagged_rows.copy()
            df["_qc_check"] = result.check_name
            df["_issue_type"] = result.issue_type
            df["_severity"] = result.severity
            all_flagged.append(df)

        if not all_flagged:
            logger.info("No flagged records to export.")
            return

        combined = pd.concat(all_flagged, ignore_index=True)
        path = os.path.join(self.output_dir, f"flagged_records_{ts}.csv")
        combined.to_csv(path, index=False)
        logger.info(f"Flagged records saved: {path} ({len(combined)} rows)")

    def _export_qc_summary(self, results: List[CheckResult], df_original: pd.DataFrame, ts: str):
        """Write summary data to CSV (Replaces Excel logic)."""
        path = os.path.join(self.output_dir, f"qc_summary_{ts}.csv")

        summary_data = []
        for r in results:
            summary_data.append({
                "Check": r.check_name,
                "Issue Type": r.issue_type,
                "Severity": r.severity,
                "Flagged Count": len(r.flagged_rows),
                "Notes": str(r.metadata),
            })
        
        summary_df = pd.DataFrame(summary_data)
        
        # Save main summary
        summary_df.to_csv(path, index=False)
        logger.info(f"QC summary saved: {path}")

        # Save Interviewer breakdown separately if it exists
        if df_original is not None:
            self._save_interviewer_csv(results, df_original, ts)

    def _save_interviewer_csv(self, results: List[CheckResult], df_original: pd.DataFrame, ts: str):
        """Saves interviewer breakdown as a separate CSV file."""
        interviewer_col = next(
            (c for c in df_original.columns if "interviewer" in c.lower()),
            None
        )
        if not interviewer_col:
            return

        rows = []
        for result in results:
            if len(result.flagged_rows) == 0:
                continue
            flagged = result.flagged_rows
            if interviewer_col not in flagged.columns:
                continue
            counts = flagged[interviewer_col].value_counts().reset_index()
            counts.columns = [interviewer_col, "flag_count"]
            counts["check_name"] = result.check_name
            rows.append(counts)

        if rows:
            interviewer_df = pd.concat(rows, ignore_index=True)
            path = os.path.join(self.output_dir, f"interviewer_breakdown_{ts}.csv")
            interviewer_df.to_csv(path, index=False)
            logger.info(f"Interviewer breakdown saved: {path}")

    def print_summary(self, results: List[CheckResult]):
        """Print a human-readable summary to console."""
        print("\n" + "=" * 60)
        print("QC ENGINE RESULTS SUMMARY")
        print("=" * 60)
        total = 0
        for r in results:
            icon = "🔴" if r.severity == "critical" else "🟡" if r.severity == "warning" else "🔵"
            count = len(r.flagged_rows)
            print(f"{icon} [{r.severity.upper()}] {r.check_name}: {count} flags")
            total += count
        print("-" * 60)
        print(f"TOTAL FLAGS: {total}")
        print("=" * 60 + "\n")
