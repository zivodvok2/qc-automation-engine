import pandas as pd

def duplicate_check(data: pd.DataFrame) -> dict:
    """Check for duplicate rows in the DataFrame."""
    total_rows = data.shape[0]
    duplicate_rows = data.duplicated().sum()
    duplicate_percentage = (duplicate_rows / total_rows) * 100 if total_rows > 0 else 0
    status = "PASS" if duplicate_rows == 0 else "WARN" if duplicate_percentage < 1 else "FAIL"
    duplicate_info = {
        "check_name": "duplicates",
        "status": status,
        "summary": f"No duplicate rows." if duplicate_rows == 0 else f"{duplicate_percentage:.2f}% duplicate rows.",
        "details": {
            "total_rows": total_rows,
            "duplicate_rows": duplicate_rows,
            "duplicate_percentage": duplicate_percentage,
        }
    }
    return duplicate_info