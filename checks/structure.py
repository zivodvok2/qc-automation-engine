import pandas as pd

def structure_check(data: pd.DataFrame) -> dict:
    is_empty = data.empty

    status = "FAIL" if is_empty else "PASS"

    return {
        "check_name": "structure",
        "status": status,
        "summary": "Dataset is empty." if is_empty else "Dataset structure looks valid.",
        "details": {
            "row_count": data.shape[0],
            "column_count": data.shape[1],
            "columns": data.columns.tolist(),
            "dtypes": data.dtypes.astype(str).to_dict(),
            "missing_values": data.isnull().sum().to_dict(),
            "is_empty": is_empty,
        }
    }
