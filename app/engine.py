from typing import List, Callable
import pandas as pd

def run_checks(data: pd.DataFrame, checks: List[Callable]) -> dict:
    results = []

    for check in checks:
        try:
            result = check(data)
            results.append(result)
        except Exception as e:
            results.append({
                "check_name": check.__name__,
                "status": "FAIL",
                "summary": "Check crashed",
                "details": {"error": str(e)}
            })

    return {
        "total_checks": len(results),
        "results": results
    }
def evaluate_pipeline(results: list) -> dict:
    total = len(results)
    fail_count = sum(1 for r in results if r["status"] == "FAIL")

    fail_ratio = (fail_count / total) * 100 if total else 0

    if fail_ratio >= 80:
        pipeline_status = "FAIL"
    elif fail_count > 0:
        pipeline_status = "WARN"
    else:
        pipeline_status = "PASS"

    return {
        "pipeline_status": pipeline_status,
        "fail_ratio": fail_ratio,
        "fail_count": fail_count
    }
