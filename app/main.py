from app.loader import load_data
from app.engine import run_checks, evaluate_pipeline

from checks.structure import structure_check
from checks.missing_values import missing_values_check
from checks.duplicates import duplicate_check

FILE_PATH ="C:\\Users\\user\\Downloads\\bestsellers-with-categories.xlsx"


df = load_data(FILE_PATH)

checks = [
    structure_check,
    missing_values_check,
    duplicate_check
]

run_result = run_checks(df, checks)
pipeline_result = evaluate_pipeline(run_result["results"])

print("PIPELINE STATUS:", pipeline_result["pipeline_status"])
print(run_result)
