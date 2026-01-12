import pandas as pd

def missing_values_check(data: pd.DataFrame) -> dict:
    """Check for missing values in the DataFrame."""
    total_cells = data.size
    total_missing=data.isnull().sum().sum()
    missing_values_per_column = data.isnull().sum().to_dict()
    columns_with_missing = data.columns[data.isnull().any()].tolist()
    overall_missing_percentage = (total_missing / total_cells) * 100 if total_cells > 0 else 0
    status= "PASS" if overall_missing_percentage ==0 else "WARN" if overall_missing_percentage <5 else "FAIL"
    missing_info = {
        "check_name": "missing_values",
        "status": status,
        "summary": f"No missing values." if overall_missing_percentage ==0 else f"{overall_missing_percentage:.2f}% overall.",
        "details":{
        "total_cells": total_cells,
        "total_missing_values": total_missing,
        "missing_values_per_column": missing_values_per_column,
        "percentage_missing_per_column": (data.isnull().mean() * 100).to_dict(),
        "columns_with_missing_values": columns_with_missing,
        }
    }
    return missing_info