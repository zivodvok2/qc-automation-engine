"""
checks/near_duplicate_checks.py — Near-duplicate respondent detection

Catches fabricated interviews that were made slightly different on purpose.
Three detection strategies:

1. Shared identifier — same phone / email across different respondent IDs
2. Demographic cluster — same combination of age+gender+location appearing
   suspiciously often (≥ min_repeats times)
3. Near-identical response pattern — rows that differ in only a few columns
   across a set of response questions (leave-one-out fingerprint matching)
"""

import pandas as pd
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("near_duplicate_checks")


class NearDuplicateCheck(BaseCheck):
    name = "near_duplicate_check"
    issue_type = "near_duplicate_respondent"
    severity = "critical"

    def __init__(
        self,
        respondent_id_column: str = None,
        shared_id_column: str = None,        # e.g. phone number
        demographic_columns: list = None,
        response_columns: list = None,
        max_diff_columns: int = 1,
        min_demo_repeats: int = 3,
    ):
        self.respondent_id_column = respondent_id_column
        self.shared_id_column     = shared_id_column
        self.demographic_columns  = demographic_columns or []
        self.response_columns     = response_columns or []
        self.max_diff_columns     = max_diff_columns
        self.min_demo_repeats     = min_demo_repeats

    def run(self, df: pd.DataFrame) -> CheckResult:
        frames = []

        if self.shared_id_column and self.shared_id_column in df.columns:
            f = self._shared_id_duplicates(df)
            if f is not None:
                frames.append(f)

        demo_cols = [c for c in self.demographic_columns if c in df.columns]
        if len(demo_cols) >= 2:
            f = self._demographic_clusters(df, demo_cols)
            if f is not None:
                frames.append(f)

        resp_cols = [c for c in self.response_columns if c in df.columns]
        if len(resp_cols) >= 3:
            f = self._response_pattern_similarity(df, resp_cols)
            if f is not None:
                frames.append(f)

        if frames:
            combined = pd.concat(frames)
            combined = combined[~combined.index.duplicated(keep="first")]
            return self._make_result(combined, {
                "shared_id_col":  self.shared_id_column,
                "demo_cols":      self.demographic_columns,
                "response_cols":  len(self.response_columns),
            })
        return self._make_result(pd.DataFrame())

    # ── Strategy 1: shared identifier ────────────────────────────────────────

    def _shared_id_duplicates(self, df: pd.DataFrame) -> pd.DataFrame | None:
        col = self.shared_id_column
        # Normalise: strip non-digit chars (handles phone formatting variations)
        cleaned = df[col].astype(str).str.replace(r"\D", "", regex=True).str.strip()
        cleaned = cleaned[cleaned.str.len() >= 6]   # ignore blanks / very short values

        dupes = cleaned[cleaned.duplicated(keep=False)]
        if dupes.empty:
            return None

        rows = df.loc[dupes.index].copy()
        rows["_near_dup_reason"] = f"Same {col} shared across multiple respondent records"
        return rows

    # ── Strategy 2: demographic cluster ──────────────────────────────────────

    def _demographic_clusters(self, df: pd.DataFrame, cols: list) -> pd.DataFrame | None:
        counts = df.groupby(cols, dropna=False).size()
        suspicious = counts[counts >= self.min_demo_repeats]
        if suspicious.empty:
            return None

        if len(cols) == 1:
            mask = df[cols[0]].isin(suspicious.index)
        else:
            idx = pd.MultiIndex.from_frame(df[cols])
            mask = idx.isin(suspicious.index)

        rows = df[mask].copy()
        rows["_near_dup_reason"] = (
            f"Demographic combination ({', '.join(cols)}) "
            f"appears ≥{self.min_demo_repeats}× — possible cloned interviews"
        )
        return rows

    # ── Strategy 3: near-identical response pattern ───────────────────────────

    def _response_pattern_similarity(self, df: pd.DataFrame, cols: list) -> pd.DataFrame | None:
        """
        Leave-one-column-out fingerprinting: for each column that could be
        the 'changed' one, hash the remaining columns and find duplicates.
        This detects rows identical except for that one column — O(n × ncols).
        """
        sub = df[cols].fillna("__null__").astype(str)
        flagged_idx: set = set()

        # Cap at 30 columns to keep it fast
        check_cols = cols[:30] if len(cols) > 30 else cols

        for skip_col in check_cols:
            remaining = [c for c in cols if c != skip_col]
            fingerprint = sub[remaining].apply(lambda row: "|".join(row), axis=1)
            dupes = fingerprint[fingerprint.duplicated(keep=False)]
            if not dupes.empty:
                flagged_idx.update(dupes.index.tolist())

        if not flagged_idx:
            return None

        rows = df.loc[list(flagged_idx)].copy()
        rows["_near_dup_reason"] = (
            f"Near-identical response pattern — identical except "
            f"≤{self.max_diff_columns} column(s): possible copy-paste fabrication"
        )
        return rows
