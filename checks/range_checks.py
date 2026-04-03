"""
range_checks.py - Checks for out-of-range numeric values
"""

import pandas as pd
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("range_checks")


class RangeCheck(BaseCheck):
    """
    Flags rows where a numeric column falls outside [min, max].
    """
    name = "range_check"
    issue_type = "out_of_range"
    severity = "warning"

    def __init__(self, rules: list):
        """
        rules: list of dicts like:
            {"column": "age", "min": 18, "max": 99}
        """
        self.rules = rules

    def run(self, df: pd.DataFrame) -> CheckResult:
        all_flagged = []

        for rule in self.rules:
            col = rule.get("column")
            min_val = rule.get("min")
            max_val = rule.get("max")

            if col not in df.columns:
                logger.warning(f"Column '{col}' not found. Skipping range check.")
                continue

            numeric_col = pd.to_numeric(df[col], errors="coerce")
            mask = pd.Series(False, index=df.index)

            if min_val is not None:
                mask |= numeric_col < min_val
            if max_val is not None:
                mask |= numeric_col > max_val

            flagged = df[mask].copy()
            flagged["_range_issue"] = col
            flagged["_value"] = numeric_col[mask]
            flagged["_expected_range"] = f"[{min_val}, {max_val}]"

            logger.info(f"[{self.name}] '{col}': {len(flagged)} out-of-range values.")
            all_flagged.append(flagged)

        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        return self._make_result(combined, {"rules_applied": len(self.rules)})


class DurationCheck(BaseCheck):
    """
    Flags interviews that are suspiciously short or long.
    """
    name = "duration_check"
    issue_type = "interview_duration"
    severity = "warning"

    def __init__(self, column: str, min_minutes: float = 5, max_minutes: float = 120):
        self.column = column
        self.min_minutes = min_minutes
        self.max_minutes = max_minutes

    def run(self, df: pd.DataFrame) -> CheckResult:
        if self.column not in df.columns:
            logger.warning(f"Duration column '{self.column}' not found.")
            return self._make_result(df.iloc[0:0])

        durations = pd.to_numeric(df[self.column], errors="coerce")
        mask = (durations < self.min_minutes) | (durations > self.max_minutes)
        flagged = df[mask].copy()
        flagged["_duration_issue"] = durations[mask]

        metadata = {
            "min_expected": self.min_minutes,
            "max_expected": self.max_minutes,
            "too_short": int((durations < self.min_minutes).sum()),
            "too_long": int((durations > self.max_minutes).sum()),
        }
        logger.info(f"[{self.name}] {len(flagged)} duration anomalies found.")
        return self._make_result(flagged, metadata)
