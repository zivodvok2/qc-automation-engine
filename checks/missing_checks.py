"""
missing_checks.py - Checks for missing / null values
"""

import pandas as pd
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("missing_checks")


class MissingValueCheck(BaseCheck):
    """
    Flags rows where any required column has a missing value.
    """
    name = "missing_value_check"
    issue_type = "missing_data"
    severity = "warning"

    def __init__(self, columns: list = None, threshold: float = None):
        """
        columns: specific columns to check (None = all columns)
        threshold: flag column if missing % exceeds this (0.0–1.0)
        """
        self.columns = columns
        self.threshold = threshold

    def run(self, df: pd.DataFrame) -> CheckResult:
        cols = self.columns or df.columns.tolist()
        cols = [c for c in cols if c in df.columns]

        if self.threshold is not None:
            # Flag columns that exceed the missing threshold
            missing_rates = df[cols].isnull().mean()
            flagged_cols = missing_rates[missing_rates > self.threshold].index.tolist()
            flagged = df[df[flagged_cols].isnull().any(axis=1)] if flagged_cols else df.iloc[0:0]
            metadata = {
                "threshold": self.threshold,
                "columns_exceeding_threshold": flagged_cols,
                "missing_rates": missing_rates[flagged_cols].to_dict() if flagged_cols else {},
            }
        else:
            # Flag any row with a null in the checked columns
            flagged = df[df[cols].isnull().any(axis=1)].copy()
            flagged["_missing_columns"] = flagged[cols].apply(
                lambda row: [c for c in cols if pd.isnull(row[c])], axis=1
            )
            metadata = {"checked_columns": cols}

        logger.info(f"[{self.name}] Flagged {len(flagged)} rows.")
        return self._make_result(flagged, metadata)


class HighMissingColumnCheck(BaseCheck):
    """
    Flags entire columns with a missing rate above the threshold.
    Returns a summary (not per-row results).
    """
    name = "high_missing_column_check"
    issue_type = "column_missing_rate"
    severity = "info"

    def __init__(self, threshold: float = 0.2):
        self.threshold = threshold

    def run(self, df: pd.DataFrame) -> CheckResult:
        missing_rates = df.isnull().mean()
        bad_cols = missing_rates[missing_rates > self.threshold]

        # Return a 1-row-per-column summary DataFrame
        summary_df = pd.DataFrame({
            "column": bad_cols.index,
            "missing_rate": bad_cols.values,
        })

        metadata = {
            "threshold": self.threshold,
            "flagged_columns": bad_cols.index.tolist(),
        }

        logger.info(f"[{self.name}] {len(bad_cols)} columns exceed {self.threshold:.0%} missing rate.")
        return self._make_result(summary_df, metadata)
