import pandas as pd

def structure_check(data: pd.DataFrame) -> dict:
    """Perform structure checks on the DataFrame."""
    structure_info = {
        "row_count": data.shape[0],
        "column_count": data.shape[1],
        "columns": data.columns.tolist(),
        "dtypes": data.dtypes.astype(str).to_dict(),
        "is_empty": data.empty,
    }
    return structure_info