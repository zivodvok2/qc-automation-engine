"""
main.py - QC Automation Engine Entry Point

Usage:
    python main.py --input data/survey_data.csv --config config/rules.json
    python main.py --input data/survey_data.xlsx --output results/
"""

import argparse
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine
from core.reporter import Reporter
from core.utils import setup_logger

logger = setup_logger(
    name="qc_engine",
    log_file="outputs/qc_engine.log"
)


def parse_args():
    parser = argparse.ArgumentParser(description="QC Automation Engine for CATI Survey Data")
    parser.add_argument("--input", required=True, help="Path to input data file (CSV/XLSX/SAV)")
    parser.add_argument("--config", default="config/rules.json", help="Path to rules config JSON")
    parser.add_argument("--output", default="outputs/", help="Directory for output files")
    parser.add_argument("--required-cols", nargs="*", help="Required columns for schema validation")
    return parser.parse_args()


def run(input_path: str, config_path: str = "config/rules.json", output_dir: str = "outputs/",
        required_cols: list = None):
    """
    Full QC pipeline:
    1. Load → 2. Clean → 3. Validate → 4. Report
    """

    logger.info("=" * 50)
    logger.info("QC ENGINE STARTING")
    logger.info("=" * 50)

    # 1. Load
    loader = DataLoader()
    df = loader.load(input_path)
    if required_cols:
        loader.validate_schema(df, required_cols)

    # 2. Clean
    cleaner = DataCleaner()
    df_clean = cleaner.clean(df)

    # 3. Validate
    engine = RuleEngine(config_path=config_path)
    results = engine.run(df_clean)

    # 4. Report
    reporter = Reporter(output_dir=output_dir)
    reporter.print_summary(results)
    reporter.generate(results, df_original=df_clean)

    logger.info("QC Engine run complete.")
    return results


if __name__ == "__main__":
    args = parse_args()
    run(
        input_path=args.input,
        config_path=args.config,
        output_dir=args.output,
        required_cols=args.required_cols,
    )
