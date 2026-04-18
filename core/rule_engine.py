"""
rule_engine.py - Config-driven orchestrator for all validation checks
"""

import pandas as pd
from typing import List
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger, load_json_config

from checks.missing_checks import MissingValueCheck, HighMissingColumnCheck
from checks.range_checks import RangeCheck, DurationCheck
from checks.logic_checks import LogicCheck, DuplicateCheck
from checks.pattern_checks import PatternCheck, AnomalyCheck
from checks.advanced_checks import (
    StraightliningCheck,
    InterviewerDurationCheck,
    InterviewerProductivityCheck,
    ConsentEligibilityCheck,
    FabricationCheck,
)
from checks.consistency_checks import ConsistencyCheck
from checks.near_duplicate_checks import NearDuplicateCheck
try:
    from checks.verbatim_checks import VerbatimQualityCheck
    _VERBATIM_AVAILABLE = True
except ImportError:
    _VERBATIM_AVAILABLE = False

logger = setup_logger("rule_engine")


class RuleEngine:
    """
    Loads rules from config dict or JSON file and runs all checks.
    """

    def __init__(self, config_path: str = "config/rules.json", config: dict = None):
        if config is not None:
            self.config = config
        else:
            self.config = load_json_config(config_path)
        self.checks: List[BaseCheck] = []
        self.results: List[CheckResult] = []
        self._build_checks()

    def _build_checks(self):
        cfg = self.config

        # ── Missing ──────────────────────────────────────────────────────────
        threshold = cfg.get("missing_threshold")
        if threshold is not None:
            self.checks.append(MissingValueCheck(threshold=threshold))
            self.checks.append(HighMissingColumnCheck(threshold=threshold))

        # ── Range ────────────────────────────────────────────────────────────
        if cfg.get("range_rules"):
            self.checks.append(RangeCheck(rules=cfg["range_rules"]))

        # ── Logic (enhanced) ─────────────────────────────────────────────────
        if cfg.get("logic_rules"):
            self.checks.append(LogicCheck(rules=cfg["logic_rules"]))

        # ── Patterns / regex ─────────────────────────────────────────────────
        if cfg.get("pattern_rules"):
            self.checks.append(PatternCheck(rules=cfg["pattern_rules"]))

        # ── Duplicates ───────────────────────────────────────────────────────
        dup = cfg.get("duplicate_check", {})
        if dup.get("enabled"):
            subset = dup.get("subset_columns") or None
            self.checks.append(DuplicateCheck(subset=subset))

        # ── Interview duration ────────────────────────────────────────────────
        dur = cfg.get("interview_duration", {})
        if dur.get("enabled"):
            self.checks.append(DurationCheck(
                column=dur["column"],
                min_minutes=dur.get("min_expected", 5),
                max_minutes=dur.get("max_expected", 120),
            ))

        # ── Statistical anomalies (IQR) ──────────────────────────────────────
        anomaly = cfg.get("anomaly_check", {})
        if anomaly.get("enabled") and anomaly.get("columns"):
            self.checks.append(AnomalyCheck(
                columns=anomaly["columns"],
                multiplier=anomaly.get("multiplier", 1.5),
            ))

        # ── Straightlining ───────────────────────────────────────────────────
        sl = cfg.get("straightlining", {})
        if sl.get("enabled") and sl.get("question_columns"):
            self.checks.append(StraightliningCheck(
                question_columns=sl["question_columns"],
                threshold=sl.get("threshold", 1.0),
                interviewer_column=sl.get("interviewer_column"),
                min_questions=sl.get("min_questions", 3),
            ))

        # ── Interviewer duration anomaly ─────────────────────────────────────
        int_dur = cfg.get("interviewer_duration_check", {})
        if int_dur.get("enabled"):
            self.checks.append(InterviewerDurationCheck(
                interviewer_column=int_dur["interviewer_column"],
                duration_column=int_dur["duration_column"],
                multiplier=int_dur.get("multiplier", 1.5),
                min_interviews=int_dur.get("min_interviews", 3),
            ))

        # ── Interviewer productivity ─────────────────────────────────────────
        int_prod = cfg.get("interviewer_productivity_check", {})
        if int_prod.get("enabled"):
            self.checks.append(InterviewerProductivityCheck(
                interviewer_column=int_prod["interviewer_column"],
                multiplier=int_prod.get("multiplier", 1.5),
                date_column=int_prod.get("date_column"),
            ))

        # ── Consent / eligibility ────────────────────────────────────────────
        consent = cfg.get("consent_eligibility_check", {})
        if consent.get("enabled"):
            self.checks.append(ConsentEligibilityCheck(
                screener_column=consent["screener_column"],
                disqualify_operator=consent.get("disqualify_operator", "!="),
                disqualify_value=consent["disqualify_value"],
                subsequent_columns=consent.get("subsequent_columns", []),
            ))

        # ── Fabrication detection ────────────────────────────────────────────
        fab = cfg.get("fabrication_check", {})
        if fab.get("enabled"):
            self.checks.append(FabricationCheck(
                id_column=fab.get("id_column"),
                numeric_columns=fab.get("numeric_columns", []),
                interviewer_column=fab.get("interviewer_column"),
                variance_threshold=fab.get("variance_threshold", 0.1),
                sequence_run_length=fab.get("sequence_run_length", 5),
            ))

        # ── Consistency check ─────────────────────────────────────────────────
        cons_rules = cfg.get("consistency_rules", [])
        if cons_rules:
            self.checks.append(ConsistencyCheck(rules=cons_rules))

        # ── Near-duplicate detection ──────────────────────────────────────────
        nd = cfg.get("near_duplicate_check", {})
        if nd.get("enabled"):
            self.checks.append(NearDuplicateCheck(
                respondent_id_column=nd.get("respondent_id_column"),
                shared_id_column=nd.get("shared_id_column"),
                demographic_columns=nd.get("demographic_columns", []),
                response_columns=nd.get("response_columns", []),
                max_diff_columns=nd.get("max_diff_columns", 1),
                min_demo_repeats=nd.get("min_demo_repeats", 3),
            ))

        # ── Verbatim quality check ──────────────────────────────────────────
        verb = cfg.get("verbatim_check", {})
        if verb.get("enabled") and _VERBATIM_AVAILABLE:
            self.checks.append(VerbatimQualityCheck(
                verbatim_columns=verb.get("verbatim_columns", []),
                model=verb.get("model", "llama3"),
                min_score=verb.get("min_score", 2),
                sample_size=verb.get("sample_size", 50),
            ))

        logger.info(f"Rule engine initialized with {len(self.checks)} checks.")

    def add_check(self, check: BaseCheck):
        """Register a custom check at runtime."""
        self.checks.append(check)

    def run(self, df: pd.DataFrame) -> List[CheckResult]:
        self.results = []
        logger.info(f"Running {len(self.checks)} checks on {len(df)} rows...")
        for check in self.checks:
            try:
                result = check.run(df)
                self.results.append(result)
                logger.info(f"✔ {check.name}: {result.flag_count} issues flagged.")
            except Exception as e:
                logger.error(f"✘ {check.name} failed: {e}", exc_info=True)
        total = sum(r.flag_count for r in self.results)
        logger.info(f"QC complete. Total flags: {total}")
        return self.results

    def get_summary(self) -> pd.DataFrame:
        return pd.DataFrame([r.summary() for r in self.results])
