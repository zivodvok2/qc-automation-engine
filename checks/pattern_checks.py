"""
pattern_checks.py - Regex and format validation checks
"""

import re
import pandas as pd
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("pattern_checks")


class PatternCheck(BaseCheck):
    """
    Flags values that don't match an expected regex pattern.
    """
    name = "pattern_check"
    issue_type = "pattern_mismatch"
    severity = "warning"

    def __init__(self, rules: list):
        """
        rules: list of dicts:
        {
            "column": "phone",
            "pattern": r"^[+]?[0-9\-\s]{7,15}$",  # noqa
            "description": "Valid phone format"
        }
        """
        self.rules = rules

    def run(self, df: pd.DataFrame) -> CheckResult:
        all_flagged = []

        for rule in self.rules:
            col = rule.get("column")
            pattern = rule.get("pattern")
            description = rule.get("description", f"{col} pattern check")

            if col not in df.columns:
                logger.warning(f"Column '{col}' not found. Skipping pattern check.")
                continue

            str_col = df[col].astype(str).where(df[col].notna(), other=pd.NA)
            compiled = re.compile(pattern)

            invalid_mask = str_col.notna() & ~str_col.apply(
                lambda x: bool(compiled.match(x)) if pd.notna(x) else True
            )

            flagged = df[invalid_mask].copy()
            flagged["_pattern_issue"] = description
            flagged["_invalid_value"] = df.loc[invalid_mask, col]

            logger.info(f"[{self.name}] '{col}': {len(flagged)} pattern violations.")
            all_flagged.append(flagged)

        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        return self._make_result(combined, {"rules_applied": len(self.rules)})


class AnomalyCheck(BaseCheck):
    """
    Flags statistical outliers using IQR method.
    """
    name = "anomaly_check"
    issue_type = "statistical_anomaly"
    severity = "info"

    def __init__(self, columns: list, multiplier: float = 1.5):
        """
        columns: numeric columns to check for outliers
        multiplier: IQR multiplier (default 1.5 = standard, 3.0 = extreme only)
        """
        self.columns = columns
        self.multiplier = multiplier

    def run(self, df: pd.DataFrame) -> CheckResult:
        all_flagged = []

        for col in self.columns:
            if col not in df.columns:
                continue

            numeric = pd.to_numeric(df[col], errors="coerce")
            q1 = numeric.quantile(0.25)
            q3 = numeric.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - self.multiplier * iqr
            upper = q3 + self.multiplier * iqr

            mask = (numeric < lower) | (numeric > upper)
            flagged = df[mask].copy()
            flagged["_anomaly_column"] = col
            flagged["_anomaly_value"] = numeric[mask]
            flagged["_anomaly_bounds"] = f"[{lower:.2f}, {upper:.2f}]"

            logger.info(f"[{self.name}] '{col}': {len(flagged)} outliers (bounds: {lower:.2f}–{upper:.2f}).")
            all_flagged.append(flagged)

        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        return self._make_result(combined, {"multiplier": self.multiplier})
