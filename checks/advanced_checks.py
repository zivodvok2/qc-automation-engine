"""
advanced_checks.py - Advanced QC checks

1. StraightliningCheck    — respondents giving same answer across many questions
2. InterviewerDurationCheck — interviewers whose pace is an outlier vs peers
3. InterviewerProductivityCheck — interviewers completing far more/fewer than peers
4. ConsentEligibilityCheck — disqualified respondents who have data in later questions
5. FabricationCheck        — suspiciously sequential or repeated numeric patterns
"""

import pandas as pd
import numpy as np
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("advanced_checks")


# ══════════════════════════════════════════════════════════════════════════════
# 1. STRAIGHTLINING CHECK
# ══════════════════════════════════════════════════════════════════════════════

class StraightliningCheck(BaseCheck):
    """
    Detects respondents (or interviewers) who gave the same answer across
    a set of questions — a sign of satisficing or data fabrication.

    Can be used two ways:
      A) Per-respondent: flag individual rows where the respondent gave
         identical answers across all question columns (threshold = 1.0
         means 100% same answer, 0.9 means 90% same, etc.)

      B) Per-interviewer: group by an interviewer column first, then check
         what % of their respondents are straightliners.

    Config example:
    {
        "question_columns": ["Q1", "Q2", "Q3", "Q4", "Q5"],
        "threshold": 0.9,               # 90%+ same answer = flag
        "interviewer_column": "int_id", # optional — also summarise by interviewer
        "min_questions": 3              # minimum columns to qualify for check
    }
    """
    name = "straightlining_check"
    issue_type = "straightlining"
    severity = "warning"

    def __init__(self, question_columns: list, threshold: float = 1.0,
                 interviewer_column: str = None, min_questions: int = 3):
        self.question_columns = question_columns
        self.threshold = threshold
        self.interviewer_column = interviewer_column
        self.min_questions = min_questions

    def run(self, df: pd.DataFrame) -> CheckResult:
        cols = [c for c in self.question_columns if c in df.columns]

        if len(cols) < self.min_questions:
            logger.warning(
                f"[{self.name}] Only {len(cols)} of {len(self.question_columns)} "
                f"question columns found — need at least {self.min_questions}."
            )
            return self._make_result(df.iloc[0:0])

        subset = df[cols].copy()

        # For each row, compute the proportion of answers that equal the modal answer
        def straightline_score(row):
            vals = row.dropna()
            if len(vals) < self.min_questions:
                return 0.0
            mode_count = vals.value_counts().iloc[0]
            return mode_count / len(vals)

        scores = subset.apply(straightline_score, axis=1)
        flagged = df[scores >= self.threshold].copy()
        flagged["_sl_score"] = scores[scores >= self.threshold].round(3)
        flagged["_sl_modal_answer"] = subset[scores >= self.threshold].apply(
            lambda row: row.dropna().value_counts().index[0]
            if len(row.dropna()) > 0 else None, axis=1
        )

        metadata = {
            "question_columns": cols,
            "threshold": self.threshold,
            "flagged_respondents": len(flagged),
            "pct_of_total": round(len(flagged) / max(len(df), 1) * 100, 1),
        }

        # Per-interviewer summary
        if self.interviewer_column and self.interviewer_column in df.columns:
            int_summary = (
                flagged.groupby(self.interviewer_column)
                .size()
                .reset_index(name="straightliner_count")
            )
            total_per_int = (
                df.groupby(self.interviewer_column)
                .size()
                .reset_index(name="total_interviews")
            )
            int_summary = int_summary.merge(total_per_int, on=self.interviewer_column)
            int_summary["straightliner_pct"] = (
                int_summary["straightliner_count"] / int_summary["total_interviews"] * 100
            ).round(1)
            metadata["interviewer_summary"] = int_summary.to_dict(orient="records")
            logger.info(
                f"[{self.name}] {len(flagged)} straightliners. "
                f"Interviewer breakdown: {len(int_summary)} interviewers affected."
            )
        else:
            logger.info(f"[{self.name}] {len(flagged)} straightliners flagged.")

        return self._make_result(flagged, metadata)


# ══════════════════════════════════════════════════════════════════════════════
# 2. INTERVIEWER DURATION ANOMALY
# ══════════════════════════════════════════════════════════════════════════════

class InterviewerDurationCheck(BaseCheck):
    """
    Flags interviewers whose average interview duration is a statistical
    outlier compared to their peers — either suspiciously fast or slow.

    Uses IQR method on per-interviewer mean durations.

    Config example:
    {
        "interviewer_column": "int_id",
        "duration_column": "duration_minutes",
        "multiplier": 1.5,        # IQR multiplier
        "min_interviews": 3       # minimum interviews to be included
    }
    """
    name = "interviewer_duration_check"
    issue_type = "interviewer_duration_anomaly"
    severity = "warning"

    def __init__(self, interviewer_column: str, duration_column: str,
                 multiplier: float = 1.5, min_interviews: int = 3):
        self.interviewer_column = interviewer_column
        self.duration_column = duration_column
        self.multiplier = multiplier
        self.min_interviews = min_interviews

    def run(self, df: pd.DataFrame) -> CheckResult:
        for col in [self.interviewer_column, self.duration_column]:
            if col not in df.columns:
                logger.warning(f"[{self.name}] Column '{col}' not found.")
                return self._make_result(df.iloc[0:0])

        df_work = df.copy()
        df_work["_dur_numeric"] = pd.to_numeric(df_work[self.duration_column], errors="coerce")

        # Per-interviewer stats
        int_stats = (
            df_work.groupby(self.interviewer_column)["_dur_numeric"]
            .agg(mean_duration="mean", interview_count="count")
            .reset_index()
        )
        int_stats = int_stats[int_stats["interview_count"] >= self.min_interviews]

        if len(int_stats) < 4:
            logger.warning(f"[{self.name}] Not enough interviewers for IQR analysis.")
            return self._make_result(df.iloc[0:0])

        q1 = int_stats["mean_duration"].quantile(0.25)
        q3 = int_stats["mean_duration"].quantile(0.75)
        iqr = q3 - q1
        lo = q1 - self.multiplier * iqr
        hi = q3 + self.multiplier * iqr

        outlier_ints = int_stats[
            (int_stats["mean_duration"] < lo) | (int_stats["mean_duration"] > hi)
        ].copy()
        outlier_ints["_duration_issue"] = outlier_ints["mean_duration"].apply(
            lambda x: "too_fast" if x < lo else "too_slow"
        )
        outlier_ints["_expected_range"] = f"[{lo:.1f}, {hi:.1f}] mins"

        # Flag all interviews by outlier interviewers
        outlier_ids = outlier_ints[self.interviewer_column].tolist()
        flagged = df[df[self.interviewer_column].isin(outlier_ids)].copy()
        flagged = flagged.merge(
            outlier_ints[[self.interviewer_column, "mean_duration",
                          "interview_count", "_duration_issue", "_expected_range"]],
            on=self.interviewer_column, how="left"
        )

        metadata = {
            "duration_column": self.duration_column,
            "bounds": f"[{lo:.1f}, {hi:.1f}]",
            "outlier_interviewers": len(outlier_ids),
            "flagged_interviews": len(flagged),
            "too_fast": int((outlier_ints["_duration_issue"] == "too_fast").sum()),
            "too_slow": int((outlier_ints["_duration_issue"] == "too_slow").sum()),
        }
        logger.info(
            f"[{self.name}] {len(outlier_ids)} outlier interviewers "
            f"({metadata['too_fast']} fast, {metadata['too_slow']} slow)."
        )
        return self._make_result(flagged, metadata)


# ══════════════════════════════════════════════════════════════════════════════
# 3. INTERVIEWER PRODUCTIVITY OUTLIERS
# ══════════════════════════════════════════════════════════════════════════════

class InterviewerProductivityCheck(BaseCheck):
    """
    Flags interviewers who completed significantly more or fewer interviews
    than their peers — could indicate data fabrication (too many) or
    low effort (too few).

    Uses IQR on interview counts per interviewer.
    """
    name = "interviewer_productivity_check"
    issue_type = "interviewer_productivity_anomaly"
    severity = "warning"

    def __init__(self, interviewer_column: str, multiplier: float = 1.5,
                 date_column: str = None):
        self.interviewer_column = interviewer_column
        self.multiplier = multiplier
        self.date_column = date_column   # optional: normalise by date

    def run(self, df: pd.DataFrame) -> CheckResult:
        if self.interviewer_column not in df.columns:
            logger.warning(f"[{self.name}] Column '{self.interviewer_column}' not found.")
            return self._make_result(df.iloc[0:0])

        counts = (
            df.groupby(self.interviewer_column)
            .size()
            .reset_index(name="interview_count")
        )

        q1 = counts["interview_count"].quantile(0.25)
        q3 = counts["interview_count"].quantile(0.75)
        iqr = q3 - q1
        lo = max(0, q1 - self.multiplier * iqr)
        hi = q3 + self.multiplier * iqr

        outliers = counts[
            (counts["interview_count"] < lo) | (counts["interview_count"] > hi)
        ].copy()
        outliers["_productivity_issue"] = outliers["interview_count"].apply(
            lambda x: "unusually_high" if x > hi else "unusually_low"
        )
        outliers["_expected_range"] = f"[{lo:.0f}, {hi:.0f}] interviews"

        outlier_ids = outliers[self.interviewer_column].tolist()
        flagged = df[df[self.interviewer_column].isin(outlier_ids)].copy()
        flagged = flagged.merge(
            outliers[[self.interviewer_column, "interview_count",
                       "_productivity_issue", "_expected_range"]],
            on=self.interviewer_column, how="left"
        )

        metadata = {
            "bounds": f"[{lo:.0f}, {hi:.0f}]",
            "outlier_interviewers": len(outlier_ids),
            "unusually_high": int((outliers["_productivity_issue"] == "unusually_high").sum()),
            "unusually_low":  int((outliers["_productivity_issue"] == "unusually_low").sum()),
        }
        logger.info(
            f"[{self.name}] {len(outlier_ids)} outlier interviewers by productivity."
        )
        return self._make_result(flagged, metadata)


# ══════════════════════════════════════════════════════════════════════════════
# 4. CONSENT / ELIGIBILITY VIOLATION CHECK
# ══════════════════════════════════════════════════════════════════════════════

class ConsentEligibilityCheck(BaseCheck):
    """
    Flags respondents who were disqualified by a screener question
    but still have data populated in subsequent questions.

    Example: if Q1 (consent) != "Yes", all following questions should be null.

    Config example:
    {
        "screener_column": "consent",
        "disqualify_operator": "!=",
        "disqualify_value": "Yes",
        "subsequent_columns": ["Q2", "Q3", "Q4", "Q5"]
    }
    """
    name = "consent_eligibility_check"
    issue_type = "eligibility_violation"
    severity = "critical"

    def __init__(self, screener_column: str, disqualify_operator: str,
                 disqualify_value, subsequent_columns: list):
        self.screener_column = screener_column
        self.disqualify_operator = disqualify_operator
        self.disqualify_value = disqualify_value
        self.subsequent_columns = subsequent_columns

    def run(self, df: pd.DataFrame) -> CheckResult:
        from checks.logic_checks import _evaluate_condition

        if self.screener_column not in df.columns:
            logger.warning(f"[{self.name}] Screener column '{self.screener_column}' not found.")
            return self._make_result(df.iloc[0:0])

        # Rows that are disqualified
        disqualified = _evaluate_condition(
            df[self.screener_column], self.disqualify_operator, self.disqualify_value
        )

        sub_cols = [c for c in self.subsequent_columns if c in df.columns]
        if not sub_cols:
            logger.warning(f"[{self.name}] No subsequent columns found.")
            return self._make_result(df.iloc[0:0])

        # Violation: disqualified but has data in any subsequent column
        has_data = df[sub_cols].notna().any(axis=1)
        violation_mask = disqualified & has_data
        flagged = df[violation_mask].copy()
        flagged["_screener_value"] = df.loc[violation_mask, self.screener_column]
        flagged["_populated_columns"] = df.loc[violation_mask, sub_cols].apply(
            lambda row: [c for c in sub_cols if pd.notna(row[c])], axis=1
        )

        metadata = {
            "screener_column": self.screener_column,
            "disqualify_condition": f"{self.screener_column} {self.disqualify_operator} {self.disqualify_value}",
            "subsequent_columns_checked": sub_cols,
            "violations": len(flagged),
        }
        logger.info(f"[{self.name}] {len(flagged)} eligibility violations.")
        return self._make_result(flagged, metadata)


# ══════════════════════════════════════════════════════════════════════════════
# 5. FABRICATION / SEQUENCE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class FabricationCheck(BaseCheck):
    """
    Detects numeric patterns that suggest fabricated data:

    A) Sequential IDs — respondent IDs that are perfectly consecutive
       (e.g., 1001, 1002, 1003... is suspicious in a random sample)

    B) Repeated numeric blocks — the same set of values appearing
       in the same order multiple times across rows

    C) Low variance columns — numeric columns where an interviewer's
       responses have suspiciously low standard deviation compared to peers
       (everyone gave nearly the same number = possible fabrication)

    Config example:
    {
        "id_column": "respondent_id",
        "numeric_columns": ["Q10", "Q11", "Q12"],
        "interviewer_column": "int_id",
        "variance_threshold": 0.1    # std dev below this % of global std = suspicious
    }
    """
    name = "fabrication_check"
    issue_type = "potential_fabrication"
    severity = "critical"

    def __init__(self, id_column: str = None, numeric_columns: list = None,
                 interviewer_column: str = None, variance_threshold: float = 0.1,
                 sequence_run_length: int = 5):
        self.id_column = id_column
        self.numeric_columns = numeric_columns or []
        self.interviewer_column = interviewer_column
        self.variance_threshold = variance_threshold
        self.sequence_run_length = sequence_run_length

    def run(self, df: pd.DataFrame) -> CheckResult:
        all_flagged = []
        metadata = {}

        # A) Sequential ID check
        if self.id_column and self.id_column in df.columns:
            ids = pd.to_numeric(df[self.id_column], errors="coerce").dropna().sort_values()
            diffs = ids.diff().dropna()
            sequential_runs = self._find_sequential_runs(ids, self.sequence_run_length)
            if sequential_runs:
                seq_idx = [idx for run in sequential_runs for idx in run]
                flagged = df.loc[df.index.isin(seq_idx)].copy()
                flagged["_fabrication_type"] = "sequential_ids"
                all_flagged.append(flagged)
                metadata["sequential_id_runs"] = len(sequential_runs)
                logger.info(
                    f"[{self.name}] {len(sequential_runs)} sequential ID runs detected."
                )

        # B) Low variance per interviewer on numeric columns
        if self.interviewer_column and self.interviewer_column in df.columns:
            num_cols = [c for c in self.numeric_columns if c in df.columns]
            for col in num_cols:
                numeric = pd.to_numeric(df[col], errors="coerce")
                global_std = numeric.std()
                if global_std == 0 or pd.isna(global_std):
                    continue

                int_std = (
                    df.assign(_num=numeric)
                    .groupby(self.interviewer_column)["_num"]
                    .std()
                    .reset_index()
                )
                int_std.columns = [self.interviewer_column, "interviewer_std"]
                int_std["global_std"] = global_std
                int_std["std_ratio"] = int_std["interviewer_std"] / global_std

                suspicious = int_std[
                    int_std["std_ratio"] < self.variance_threshold
                ]
                if not suspicious.empty:
                    susp_ids = suspicious[self.interviewer_column].tolist()
                    flagged = df[df[self.interviewer_column].isin(susp_ids)].copy()
                    flagged["_fabrication_type"] = f"low_variance_{col}"
                    flagged["_column_checked"] = col
                    all_flagged.append(flagged)
                    metadata[f"low_variance_{col}_interviewers"] = len(susp_ids)
                    logger.info(
                        f"[{self.name}] Low variance on '{col}': "
                        f"{len(susp_ids)} suspicious interviewers."
                    )

        combined = (
            pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        )
        return self._make_result(combined, metadata)

    def _find_sequential_runs(self, sorted_ids: pd.Series, min_length: int) -> list:
        """Find runs of consecutive integers of at least min_length."""
        runs = []
        current_run = [sorted_ids.index[0]]

        for i in range(1, len(sorted_ids)):
            if sorted_ids.iloc[i] == sorted_ids.iloc[i - 1] + 1:
                current_run.append(sorted_ids.index[i])
            else:
                if len(current_run) >= min_length:
                    runs.append(current_run)
                current_run = [sorted_ids.index[i]]

        if len(current_run) >= min_length:
            runs.append(current_run)

        return runs
