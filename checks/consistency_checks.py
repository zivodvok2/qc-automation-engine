"""
checks/consistency_checks.py — Cross-column response consistency

Flags respondents who contradict themselves within the same interview.
Uses the same IF/THEN rule schema as logic_checks so rules can be
built with the same UI or natural-language builder.

Examples of consistency violations:
  - Age < 18 but marital_status is filled
  - employment == "Never worked" but job_title is filled
  - Q_children == "No" but school_fees_amount > 0
"""

import pandas as pd
from checks.logic_checks import _evaluate_condition, _build_mask
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("consistency_checks")


class ConsistencyCheck(BaseCheck):
    """
    Cross-column logical consistency. Each rule has the same schema as
    a logic_rule: if_conditions (ANDed) → then_conditions must all hold.
    Violations = IF is true AND at least one THEN is false.
    """

    name = "consistency_check"
    issue_type = "response_inconsistency"
    severity = "warning"

    def __init__(self, rules: list):
        self.rules = rules

    def run(self, df: pd.DataFrame) -> CheckResult:
        flagged_frames = []

        for rule in self.rules:
            if_conds   = rule.get("if_conditions", [])
            then_conds = rule.get("then_conditions", [])
            desc       = rule.get("description", "Consistency rule")

            if not if_conds or not then_conds:
                continue

            # Rows where the IF side triggers
            if_mask = _build_mask(df, if_conds)
            triggered = df[if_mask]
            if triggered.empty:
                continue

            # Flag rows where any THEN condition is violated
            for cond in then_conds:
                col = cond.get("column")
                if col not in df.columns:
                    logger.warning(f"Consistency check: column '{col}' not found — skipping")
                    continue
                then_met = _evaluate_condition(triggered[col], cond.get("operator", "not_null"), cond.get("value"))
                violated = triggered[~then_met].copy()
                if not violated.empty:
                    violated["_consistency_rule"] = desc
                    violated["_failed_column"] = col
                    flagged_frames.append(violated)

        if flagged_frames:
            combined = pd.concat(flagged_frames)
            # De-duplicate on original index but keep first occurrence of each rule
            combined = combined[~combined.index.duplicated(keep="first")]
            return self._make_result(combined, {"rules_checked": len(self.rules)})

        return self._make_result(pd.DataFrame(), {"rules_checked": len(self.rules)})
