import pandas as pd
import openpyxl

def load_data(file_path: str):
    file_path=file_path.lower()
    if file_path.endswith('.csv'):
        data = pd.read_csv(file_path)
    elif file_path.endswith(('.xlsx', '.xls')):
        data = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Please use .csv or .xlsx files.")
    return data