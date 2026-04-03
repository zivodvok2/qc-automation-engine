"""
verbatim_checks.py — Verbatim response quality checks via Ollama (free local LLM)

Requires Ollama running locally: https://ollama.com
Pull a model first: ollama pull llama3

If Ollama is not running, the check gracefully skips with an info message.
"""

import json
import pandas as pd
import requests
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("verbatim_checks")

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"


def _ollama_available(model: str = DEFAULT_MODEL) -> bool:
    """Check if Ollama is running and the model is available."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code != 200:
            return False
        models = [m["name"].split(":")[0] for m in r.json().get("models", [])]
        return model.split(":")[0] in models
    except Exception:
        return False


def _query_ollama(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Send a prompt to Ollama and return the response text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def _score_verbatim(text: str, model: str) -> dict:
    """
    Ask the LLM to score a single verbatim response.
    Returns a dict with scores and flags.
    """
    prompt = f"""You are a survey data quality checker. Evaluate the following verbatim survey response.
Score it on these dimensions (each 1-5, where 5=excellent, 1=poor):
- grammar: grammatical correctness
- coherence: does it make sense as an answer?
- relevance: appears to be a genuine answer (not gibberish/random characters)
- length_quality: appropriate length (not too short/vague, not copy-pasted filler)

Also flag if it appears to be:
- gibberish (random letters or characters): true/false
- copy_paste (identical or near-identical filler text): true/false
- too_short (under 3 meaningful words): true/false

Respond ONLY with valid JSON. No explanation.
Example: {{"grammar":4,"coherence":3,"relevance":5,"length_quality":2,"gibberish":false,"copy_paste":false,"too_short":true}}

Response to evaluate: "{text}"

JSON:"""
    try:
        raw = _query_ollama(prompt, model)
        # Extract JSON from response
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {}
        return json.loads(raw[start:end])
    except Exception as e:
        logger.warning(f"Ollama scoring failed: {e}")
        return {}


class VerbatimQualityCheck(BaseCheck):
    """
    Uses a local Ollama LLM to evaluate open-ended verbatim responses for:
    - Grammar quality
    - Coherence
    - Relevance (not gibberish)
    - Appropriate length
    - Gibberish / copy-paste flags

    Requires Ollama running locally with a model pulled.
    Install: https://ollama.com  |  Model: ollama pull llama3

    Config example:
    {
        "verbatim_columns": ["Q10_verbatim", "comments"],
        "model": "llama3",
        "min_score": 2,          # flag responses scoring below this on any dimension
        "sample_size": 50,       # only check a random sample (for speed)
        "interviewer_column": "interviewer_id"
    }
    """
    name      = "verbatim_quality_check"
    issue_type = "verbatim_quality"
    severity  = "warning"

    def __init__(self, verbatim_columns: list, model: str = DEFAULT_MODEL,
                 min_score: int = 2, sample_size: int = 50,
                 interviewer_column: str = None):
        self.verbatim_columns   = verbatim_columns
        self.model              = model
        self.min_score          = min_score
        self.sample_size        = sample_size
        self.interviewer_column = interviewer_column

    def run(self, df: pd.DataFrame) -> CheckResult:
        if not _ollama_available(self.model):
            logger.warning(
                f"[{self.name}] Ollama not running or model '{self.model}' not found. "
                f"Install Ollama and run: ollama pull {self.model}"
            )
            return self._make_result(df.iloc[0:0], {
                "status": "skipped",
                "reason": f"Ollama not available. Install from https://ollama.com and run: ollama pull {self.model}",
            })

        cols = [c for c in self.verbatim_columns if c in df.columns]
        if not cols:
            return self._make_result(df.iloc[0:0], {"status": "skipped", "reason": "No verbatim columns found"})

        # Sample for speed
        sample = df.sample(min(self.sample_size, len(df)), random_state=42) if len(df) > self.sample_size else df.copy()

        all_flagged = []
        scores_accumulator = []

        for col in cols:
            logger.info(f"[{self.name}] Checking '{col}' ({len(sample)} responses)...")
            for idx, row in sample.iterrows():
                text = str(row[col]) if pd.notna(row[col]) else ""
                if not text or text.strip() in ("", "nan", "None"):
                    continue

                scores = _score_verbatim(text, self.model)
                if not scores:
                    continue

                scores_accumulator.append(scores)

                # Flag if any quality score is below threshold OR if a flag is set
                is_flagged = (
                    any(scores.get(k, 5) < self.min_score
                        for k in ["grammar", "coherence", "relevance", "length_quality"])
                    or scores.get("gibberish", False)
                    or scores.get("copy_paste", False)
                    or scores.get("too_short", False)
                )

                if is_flagged:
                    flagged_row = df.loc[[idx]].copy()
                    flagged_row["_verbatim_column"]    = col
                    flagged_row["_verbatim_text"]      = text[:200]
                    flagged_row["_grammar_score"]      = scores.get("grammar")
                    flagged_row["_coherence_score"]    = scores.get("coherence")
                    flagged_row["_relevance_score"]    = scores.get("relevance")
                    flagged_row["_length_quality"]     = scores.get("length_quality")
                    flagged_row["_gibberish"]          = scores.get("gibberish", False)
                    flagged_row["_copy_paste"]         = scores.get("copy_paste", False)
                    flagged_row["_too_short"]          = scores.get("too_short", False)
                    all_flagged.append(flagged_row)

        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]

        # Aggregate stats
        meta = {
            "model": self.model,
            "columns_checked": cols,
            "responses_evaluated": len(scores_accumulator),
            "flagged": len(combined),
            "status": "completed",
        }
        if scores_accumulator:
            for dim in ["grammar", "coherence", "relevance", "length_quality"]:
                vals = [s[dim] for s in scores_accumulator if dim in s]
                if vals:
                    meta[f"avg_{dim}"] = round(sum(vals) / len(vals), 2)

        # Per-interviewer breakdown
        if self.interviewer_column and self.interviewer_column in df.columns and not combined.empty:
            int_sum = (combined.groupby(self.interviewer_column).size()
                       .reset_index(name="flagged_verbatim_count"))
            meta["interviewer_summary"] = int_sum.to_dict(orient="records")

        logger.info(f"[{self.name}] {len(combined)} low-quality responses flagged.")
        return self._make_result(combined, meta)
