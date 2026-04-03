"""
logic_checks.py - Conditional / skip-logic consistency checks

Supports rich conditions on both IF and THEN sides:
  operators: >, <, ==, !=, >=, <=, is_null, not_null, is_numeric,
             is_string, in_list, not_in_list
Multiple if-conditions are AND-ed together.
Multiple then-conditions are all evaluated independently.
"""

import pandas as pd
import numpy as np
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("logic_checks")


# ── Condition evaluator ───────────────────────────────────────────────────────

def _evaluate_condition(series: pd.Series, operator: str, value=None) -> pd.Series:
    """
    Evaluate a single condition against a Series.
    Returns a boolean Series — True means the condition IS met.
    """
    op = operator.strip().lower()

    if op == "is_null":
        return series.isna()
    if op == "not_null":
        return series.notna()
    if op == "is_numeric":
        return pd.to_numeric(series, errors="coerce").notna()
    if op == "is_string":
        return series.apply(
            lambda x: isinstance(x, str) and not str(x).replace(".", "").lstrip("-").isdigit()
        )
    if op == "in_list":
        items = [str(v).strip() for v in (value if isinstance(value, list) else [value])]
        return series.astype(str).isin(items)
    if op == "not_in_list":
        items = [str(v).strip() for v in (value if isinstance(value, list) else [value])]
        return ~series.astype(str).isin(items)

    # Numeric comparisons
    num = pd.to_numeric(series, errors="coerce")
    try:
        val = float(value)
    except (TypeError, ValueError):
        # Fall back to string comparison
        s = series.astype(str)
        v = str(value)
        if op in ("==", "eq"): return s == v
        if op in ("!=", "ne"): return s != v
        logger.warning(f"Cannot apply numeric operator '{op}' to non-numeric value '{value}'")
        return pd.Series(False, index=series.index)

    if op in (">",  "gt"):  return num > val
    if op in ("<",  "lt"):  return num < val
    if op in (">=", "gte"): return num >= val
    if op in ("<=", "lte"): return num <= val
    if op in ("==", "eq"):
        return (num == val) | (series.astype(str) == str(value))
    if op in ("!=", "ne"):
        return (num != val) & (series.astype(str) != str(value))

    logger.warning(f"Unknown operator: '{op}'")
    return pd.Series(False, index=series.index)


def _build_mask(df: pd.DataFrame, conditions: list) -> pd.Series:
    """AND together multiple conditions."""
    mask = pd.Series(True, index=df.index)
    for cond in conditions:
        col = cond.get("column")
        op  = cond.get("operator", "not_null")
        val = cond.get("value")
        if col not in df.columns:
            logger.warning(f"Column '{col}' not found — skipping condition.")
            continue
        mask = mask & _evaluate_condition(df[col], op, val)
    return mask


# ── Enhanced LogicCheck ───────────────────────────────────────────────────────

class LogicCheck(BaseCheck):
    """
    Validates conditional logic rules with rich multi-variable support.

    Rule format:
    {
        "description": "Under-18 should not be married or have salary",
        "if_conditions": [
            {"column": "age", "operator": "<", "value": 18}
        ],
        "then_conditions": [
            {"column": "married", "operator": "is_null"},
            {"column": "salary",  "operator": "is_null"}
        ]
    }

    Supported operators:
        >, <, >=, <=, ==, !=
        is_null, not_null
        is_numeric, is_string
        in_list, not_in_list  (pass value as a list)
    """
    name = "logic_check"
    issue_type = "logic_violation"
    severity = "critical"

    def __init__(self, rules: list):
        self.rules = rules

    def run(self, df: pd.DataFrame) -> CheckResult:
        all_flagged = []

        for rule in self.rules:
            desc       = rule.get("description", "Unnamed logic rule")
            if_conds   = rule.get("if_conditions", [])
            then_conds = rule.get("then_conditions", [])

            # ── Backwards-compatible legacy format ──────────────────────────
            if not if_conds and rule.get("if_column"):
                if_conds = [{"column": rule["if_column"],
                             "operator": "==",
                             "value": rule.get("if_value")}]
            if not then_conds and rule.get("then_column"):
                legacy_op = rule.get("then_condition", "must_be_null")
                op = "is_null" if legacy_op == "must_be_null" else "not_null"
                then_conds = [{"column": rule["then_column"], "operator": op}]

            if not if_conds or not then_conds:
                logger.warning(f"Rule '{desc}' is incomplete — skipping.")
                continue

            # Rows where ALL if-conditions are met
            trigger_mask = _build_mask(df, if_conds)
            triggered_df = df[trigger_mask]

            if triggered_df.empty:
                continue

            # Each then-condition is checked independently
            for then_cond in then_conds:
                col = then_cond.get("column")
                op  = then_cond.get("operator", "not_null")
                val = then_cond.get("value")

                if col not in df.columns:
                    logger.warning(f"Then-column '{col}' not found — skipping.")
                    continue

                # Violation: triggered row does NOT meet the then-condition
                meets = _evaluate_condition(triggered_df[col], op, val)
                violated = triggered_df[~meets].copy()

                if violated.empty:
                    continue

                violated["_logic_rule"]         = desc
                violated["_violated_column"]    = col
                violated["_violated_condition"] = (
                    f"{col} {op} {val if val is not None else ''}"
                )
                all_flagged.append(violated)
                logger.info(
                    f"[{self.name}] '{desc}' → '{col} {op}': {len(violated)} violations."
                )

        combined = (
            pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        )
        return self._make_result(combined, {"rules_applied": len(self.rules)})


# ── DuplicateCheck ────────────────────────────────────────────────────────────

class DuplicateCheck(BaseCheck):
    """Flags duplicate records based on specified key columns."""
    name = "duplicate_check"
    issue_type = "duplicate_record"
    severity = "critical"

    def __init__(self, subset=None):
        self.subset = subset

    def run(self, df: pd.DataFrame) -> CheckResult:
        subset = (
            [c for c in self.subset if c in df.columns]
            if self.subset else df.columns.tolist()
        )
        key = df[subset].fillna("__NA__").astype(str).apply("|".join, axis=1)
        dupes = df[key.duplicated(keep=False)].copy()
        if not dupes.empty:
            dupes["_dupe_key"] = str(subset)
        return self._make_result(dupes, {
            "subset": subset,
            "duplicate_count": len(dupes),
        })
