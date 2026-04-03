"""
validator.py - Base check class and result schema
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from abc import ABC, abstractmethod


@dataclass
class CheckResult:
    """
    Standardized output from any validation check.
    """
    check_name: str
    issue_type: str
    flagged_rows: pd.DataFrame
    severity: str = "warning"       # "info" | "warning" | "critical"
    metadata: dict = field(default_factory=dict)

    @property
    def flag_count(self) -> int:
        return len(self.flagged_rows)

    def summary(self) -> dict:
        return {
            "check_name": self.check_name,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "flagged_count": self.flag_count,
            **self.metadata,
        }


class BaseCheck(ABC):
    """
    Abstract base class for all validation checks.
    All checks must implement run() and return a CheckResult.
    """

    name: str = "base_check"
    issue_type: str = "generic"
    severity: str = "warning"

    @abstractmethod
    def run(self, df: pd.DataFrame) -> CheckResult:
        """
        Execute the check on the given DataFrame.
        Returns a CheckResult with flagged rows.
        """
        raise NotImplementedError

    def _make_result(self, flagged: pd.DataFrame, metadata: Optional[dict] = None) -> CheckResult:
        """Helper to build a CheckResult from flagged rows."""
        return CheckResult(
            check_name=self.name,
            issue_type=self.issue_type,
            flagged_rows=flagged,
            severity=self.severity,
            metadata=metadata or {},
        )
