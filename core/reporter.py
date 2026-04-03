"""
reporter.py - Generates flagged records CSV and QC summary Excel report
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
    2. qc_summary.xlsx      - aggregated summary + per-interviewer breakdown
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
            if result.flag_count == 0:
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
        """Write Excel workbook with summary sheet + optional interviewer sheet."""
        path = os.path.join(self.output_dir, f"qc_summary_{ts}.xlsx")

        summary_data = []
        for r in results:
            summary_data.append({
                "Check": r.check_name,
                "Issue Type": r.issue_type,
                "Severity": r.severity,
                "Flagged Count": r.flag_count,
                "Notes": str(r.metadata),
            })
        summary_df = pd.DataFrame(summary_data)

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, sheet_name="QC Summary", index=False)

            # Per-interviewer breakdown (if interviewer_id column exists)
            if df_original is not None:
                self._write_interviewer_sheet(writer, results, df_original)

            # Flag count by severity
            sev_df = summary_df.groupby("Severity")["Flagged Count"].sum().reset_index()
            sev_df.to_excel(writer, sheet_name="By Severity", index=False)

        logger.info(f"QC summary saved: {path}")

    def _write_interviewer_sheet(self, writer, results: List[CheckResult], df_original: pd.DataFrame):
        """Add per-interviewer flag breakdown if interviewer_id column is present."""
        interviewer_col = next(
            (c for c in df_original.columns if "interviewer" in c.lower()),
            None
        )
        if not interviewer_col:
            return

        rows = []
        for result in results:
            if result.flag_count == 0:
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
            interviewer_df.to_excel(writer, sheet_name="Interviewer Breakdown", index=False)
            logger.info("Interviewer breakdown sheet written.")

    def print_summary(self, results: List[CheckResult]):
        """Print a human-readable summary to console."""
        print("\n" + "=" * 60)
        print("QC ENGINE RESULTS SUMMARY")
        print("=" * 60)
        total = 0
        for r in results:
            icon = "🔴" if r.severity == "critical" else "🟡" if r.severity == "warning" else "🔵"
            print(f"{icon} [{r.severity.upper()}] {r.check_name}: {r.flag_count} flags")
            total += r.flag_count
        print("-" * 60)
        print(f"TOTAL FLAGS: {total}")
        print("=" * 60 + "\n")
