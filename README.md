# DataSense — Survey QC Engine

**Version 2.0.0** | Python · Streamlit · Plotly

A modular, production-grade Quality Control system for CATI survey data.
Upload a CSV or Excel file and get instant QC reports, EDA charts, logic checks,
straightlining analysis, and more — with a clean drag-and-drop interface.

---

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Project structure

```
datasense/
│
├── app.py                        ← Thin Streamlit entry point (UI wiring only)
├── main.py                       ← CLI entry point (headless pipeline)
├── requirements.txt
│
├── ui/                           ← All Streamlit UI code
│   ├── sidebar.py                ← File upload, QC settings, all check toggles
│   ├── onboarding.py             ← First-time user step-by-step guide
│   ├── settings.py               ← Theme, Ollama status, version, feedback
│   ├── components/
│   │   └── drag_drop.py          ← Reusable drag-and-drop column selector
│   └── tabs/
│       ├── qc_tab.py             ← QC Report tab (severity-grouped results)
│       ├── logic_tab.py          ← Logic Checks tab (rule builder with drag-drop)
│       ├── straightlining_tab.py ← Straightlining tab (base var + question cols)
│       ├── eda_tab.py            ← EDA tab (Plotly charts, multi-variable)
│       └── data_tab.py           ← Data Preview tab (search + column filter)
│
├── core/                         ← Engine (no Streamlit dependencies)
│   ├── loader.py                 ← CSV / XLSX / SAV ingestion
│   ├── cleaner.py                ← Null normalisation, whitespace, type coercion
│   ├── validator.py              ← BaseCheck + CheckResult base classes
│   ├── rule_engine.py            ← Config-driven orchestrator for all checks
│   ├── reporter.py               ← Excel / CSV output generation
│   └── utils.py                  ← Logger, config loader, helpers
│
├── checks/                       ← One file per check category
│   ├── missing_checks.py         ← MissingValueCheck, HighMissingColumnCheck
│   ├── range_checks.py           ← RangeCheck, DurationCheck
│   ├── logic_checks.py           ← LogicCheck (rich operators), DuplicateCheck
│   ├── pattern_checks.py         ← PatternCheck (regex), AnomalyCheck (IQR)
│   ├── advanced_checks.py        ← StraightliningCheck, InterviewerDurationCheck,
│   │                                InterviewerProductivityCheck,
│   │                                ConsentEligibilityCheck, FabricationCheck
│   └── verbatim_checks.py        ← VerbatimQualityCheck (Ollama LLM — NEW)
│
├── config/
│   ├── rules.json                ← Default QC rules (edit to customise per project)
│   └── themes.json               ← Dark / Light / Midnight theme definitions (NEW)
│
├── assets/
│   ├── onboarding_steps.json     ← Step-by-step first-time guide content (NEW)
│   └── app_version.json          ← Version and changelog (NEW)
│
└── tests/
    └── test_validations.py       ← Unit tests for all check classes
```

---

## What changed in v2.0

### New files
| File | Description |
|------|-------------|
| `ui/sidebar.py` | Extracted from app.py — all sidebar logic |
| `ui/onboarding.py` | Step-by-step first-run guide, skippable |
| `ui/settings.py` | Theme switcher, Ollama status, version, feedback |
| `ui/components/drag_drop.py` | Reusable drag-and-drop column selector component |
| `ui/tabs/qc_tab.py` | QC Report tab |
| `ui/tabs/logic_tab.py` | Logic Checks tab with interactive rule builder |
| `ui/tabs/straightlining_tab.py` | Straightlining with base variable selection |
| `ui/tabs/eda_tab.py` | EDA with Plotly charts (bar, line, scatter, heatmap, box, histogram) |
| `ui/tabs/data_tab.py` | Data Preview tab |
| `checks/verbatim_checks.py` | Grammar/coherence check via Ollama LLM |
| `config/themes.json` | Dark, Light, Midnight Blue theme definitions |
| `assets/onboarding_steps.json` | Onboarding guide content |
| `assets/app_version.json` | Version and changelog |

### Modified files
| File | Change |
|------|--------|
| `app.py` | Now a thin entry point — imports from `ui/` only, no engine code |
| `core/rule_engine.py` | Added VerbatimQualityCheck support |
| `checks/logic_checks.py` | Enhanced with rich operators, multi-condition IF/THEN, DuplicateCheck NA fix |
| `requirements.txt` | Added `plotly`, `requests` |

### Deleted / replaced
| File | Status |
|------|--------|
| Old monolithic `app.py` (500+ lines) | Replaced by modular `ui/` structure |

### Unchanged
`core/loader.py`, `core/cleaner.py`, `core/validator.py`, `core/reporter.py`,
`core/utils.py`, `checks/missing_checks.py`, `checks/range_checks.py`,
`checks/pattern_checks.py`, `checks/advanced_checks.py`, `main.py`, `tests/`

---

## Features

### QC checks
| Check | Description |
|-------|-------------|
| Missing values | Flags rows/columns above a configurable missing % threshold |
| Range checks | Flags values outside expected min/max bounds per column |
| Logic checks | If column A meets condition → column B must meet condition. Supports `>`, `<`, `>=`, `<=`, `==`, `!=`, `is_null`, `not_null`, `is_numeric`, `is_string`, `in_list`, `not_in_list`. Multi-condition IF blocks, multi-column THEN blocks |
| Duplicate detection | Exact duplicate rows, configurable subset of columns |
| Pattern checks | Regex validation (phone, email, custom patterns) |
| Statistical anomalies | IQR-based outlier detection per column |
| Interview duration | Min/max bounds on interview duration |
| Straightlining | Detects respondents giving identical answers across a question battery, with per-interviewer breakdown |
| Interviewer duration anomaly | IQR on per-interviewer mean duration vs peers |
| Interviewer productivity | IQR on interview counts per interviewer |
| Consent/eligibility | Disqualified respondents with data in subsequent questions |
| Fabrication detection | Sequential IDs + low-variance numeric answers per interviewer |
| Verbatim quality | Grammar, coherence, relevance scoring via local Ollama LLM |

### UI features
- **Drag-and-drop column selector** — visible column panel on every tab; drag into any field
- **Logic Checks tab** — interactive rule builder; see violations grouped by rule
- **Straightlining tab** — select base variable (e.g. interviewer ID) and question columns
- **EDA tab** — bar, line, scatter, histogram, box, heatmap charts via Plotly; aggregate by sum/mean/count; multi-variable support
- **Onboarding guide** — dismissible step-by-step tooltip for first-time users
- **Settings panel** — theme switcher, Ollama status/model selector, version, feedback, sign-in placeholder
- **Export** — one-click Excel report with QC flags, EDA summary, clean data snapshot

---

## Verbatim checks (Ollama)

Verbatim checks use a free, local LLM — no API key, no cost.

1. Install Ollama: https://ollama.com
2. Pull a model: `ollama pull llama3`
3. Start Ollama: `ollama serve`
4. Enable "Verbatim quality check" in the DataSense sidebar

DataSense will show Ollama status in **Settings** and use the selected model.
If Ollama is not running, the check is skipped gracefully with a message.

---

## Logic rule format (rules.json / sidebar)

New multi-condition format:
```json
{
  "description": "Under 18 should not be married or have salary",
  "if_conditions": [
    {"column": "age", "operator": "<", "value": 18}
  ],
  "then_conditions": [
    {"column": "married", "operator": "is_null"},
    {"column": "salary",  "operator": "is_null"}
  ]
}
```

Legacy single-condition format still works unchanged.

### Supported operators
`>`, `<`, `>=`, `<=`, `==`, `!=`, `is_null`, `not_null`, `is_numeric`, `is_string`, `in_list`, `not_in_list`

---

## CLI usage (headless)

```bash
python main.py --input data/survey.csv --config config/rules.json --output outputs/
```

---

## Adding a custom check

1. Create a class in the relevant `checks/` file (or a new file)
2. Inherit from `BaseCheck`, implement `run(self, df) -> CheckResult`
3. Register it in `core/rule_engine.py` under `_build_checks()`

```python
class MyCheck(BaseCheck):
    name = "my_check"
    issue_type = "custom"
    severity = "warning"

    def run(self, df: pd.DataFrame) -> CheckResult:
        flagged = df[df["some_column"].isna()].copy()
        return self._make_result(flagged, {"custom_key": "value"})
```

---

## Deploy on Streamlit Cloud

1. Push this folder to GitHub
2. Go to share.streamlit.io → New app → select repo → set main file: `app.py`
3. Done — get a public URL like `your-app.streamlit.app`

Note: Verbatim checks (Ollama) require a local machine. They are gracefully skipped on Streamlit Cloud.
