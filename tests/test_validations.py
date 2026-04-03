"""
test_validations.py - Unit tests for all validation checks
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pandas as pd
import numpy as np

from checks.missing_checks import MissingValueCheck, HighMissingColumnCheck
from checks.range_checks import RangeCheck, DurationCheck
from checks.logic_checks import LogicCheck, DuplicateCheck
from checks.pattern_checks import PatternCheck, AnomalyCheck


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "respondent_id": [1, 2, 3, 4, 5],
        "age": [25, 150, 30, -1, 45],
        "Q5": ["Yes", "No", "No", "Yes", "No"],
        "Q6": ["Answer", "Should be null", None, None, "Also wrong"],
        "phone": ["555-1234", "not-a-phone", "+44 7700 900123", "bad", "123-456-7890"],
        "email": ["a@b.com", "notanemail", "x@y.org", "bad", "valid@test.com"],
        "duration_minutes": [20, 2, 95, 130, 30],
        "score": [5, 3, 100, 2, 7],
        "interviewer_id": ["INT01", "INT01", "INT02", "INT02", "INT03"],
    })


@pytest.fixture
def missing_df():
    return pd.DataFrame({
        "a": [1, None, 3, None, 5],
        "b": [None, None, None, None, None],
        "c": [1, 2, 3, 4, 5],
    })


# ─── Missing Checks ──────────────────────────────────────────────────────────

def test_missing_value_check_flags_rows(missing_df):
    check = MissingValueCheck(columns=["a", "b"])
    result = check.run(missing_df)
    assert result.flag_count > 0
    assert result.check_name == "missing_value_check"

def test_high_missing_column_check(missing_df):
    check = HighMissingColumnCheck(threshold=0.5)
    result = check.run(missing_df)
    assert "b" in result.metadata["flagged_columns"]

def test_missing_check_no_issues():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    check = MissingValueCheck()
    result = check.run(df)
    assert result.flag_count == 0


# ─── Range Checks ────────────────────────────────────────────────────────────

def test_range_check_flags_out_of_bounds(sample_df):
    rules = [{"column": "age", "min": 18, "max": 99}]
    check = RangeCheck(rules=rules)
    result = check.run(sample_df)
    assert result.flag_count >= 2  # 150 and -1

def test_range_check_missing_column():
    df = pd.DataFrame({"other": [1, 2, 3]})
    check = RangeCheck(rules=[{"column": "age", "min": 0, "max": 100}])
    result = check.run(df)
    assert result.flag_count == 0

def test_duration_check(sample_df):
    check = DurationCheck(column="duration_minutes", min_minutes=5, max_minutes=120)
    result = check.run(sample_df)
    assert result.flag_count >= 2  # 2 (too short) and 130 (too long)
    assert result.metadata["too_short"] == 1
    assert result.metadata["too_long"] == 1


# ─── Logic Checks ────────────────────────────────────────────────────────────

def test_logic_check_must_be_null(sample_df):
    rules = [{
        "if_column": "Q5",
        "if_value": "No",
        "then_column": "Q6",
        "then_condition": "must_be_null",
        "description": "If Q5=No, Q6 must be null"
    }]
    check = LogicCheck(rules=rules)
    result = check.run(sample_df)
    assert result.flag_count == 2  # rows 1 and 4 (Q5=No, Q6 not null)

def test_duplicate_check_flags_dupes():
    df = pd.DataFrame({
        "respondent_id": [1, 2, 2, 3, 3],
        "name": ["A", "B", "B", "C", "C"]
    })
    check = DuplicateCheck(subset=["respondent_id"])
    result = check.run(df)
    assert result.flag_count == 4

def test_duplicate_check_no_dupes():
    df = pd.DataFrame({"respondent_id": [1, 2, 3]})
    check = DuplicateCheck(subset=["respondent_id"])
    result = check.run(df)
    assert result.flag_count == 0


# ─── Pattern Checks ──────────────────────────────────────────────────────────

def test_pattern_check_email(sample_df):
    rules = [{"column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$", "description": "Email format"}]
    check = PatternCheck(rules=rules)
    result = check.run(sample_df)
    assert result.flag_count == 2  # "notanemail" and "bad"

def test_anomaly_check_iqr():
    df = pd.DataFrame({
        "score": [5, 5, 5, 5, 5, 5, 5, 5, 5, 100]  # 100 is an outlier
    })
    check = AnomalyCheck(columns=["score"])
    result = check.run(df)
    assert result.flag_count >= 1


# ─── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
