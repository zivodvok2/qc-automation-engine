"""
loader.py - Data ingestion for CSV, Excel, and SPSS files
"""

import pandas as pd
import os
from core.utils import setup_logger

logger = setup_logger("loader")


class DataLoader:
    """
    Loads survey data from various file formats.
    Supported: .csv, .xlsx, .xls, .sav (SPSS)
    """

    SUPPORTED_FORMATS = {
        ".csv": "_load_csv",
        ".xlsx": "_load_excel",
        ".xls": "_load_excel",
        ".sav": "_load_spss",
    }

    def load(self, filepath: str) -> pd.DataFrame:
        """
        Load data from the given file path.
        Returns a pandas DataFrame.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")

        ext = os.path.splitext(filepath)[-1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported file format: {ext}. Supported: {list(self.SUPPORTED_FORMATS)}")

        loader_method = getattr(self, self.SUPPORTED_FORMATS[ext])
        logger.info(f"Loading file: {filepath} (format: {ext})")
        df = loader_method(filepath)
        logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns.")
        return df

    def _load_csv(self, filepath: str) -> pd.DataFrame:
        return pd.read_csv(filepath, low_memory=False)

    def _load_excel(self, filepath: str) -> pd.DataFrame:
        return pd.read_excel(filepath)

    def _load_spss(self, filepath: str) -> pd.DataFrame:
        try:
            import pyreadstat
            df, _ = pyreadstat.read_sav(filepath)
            return df
        except ImportError:
            raise ImportError("pyreadstat is required for SPSS files. Run: pip install pyreadstat")

    def validate_schema(self, df: pd.DataFrame, required_columns: list) -> None:
        """
        Check that required columns are present.
        Raises ValueError if any are missing.
        """
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        logger.info("Schema validation passed.")

    def load_from_buffer(self, uploaded_file) -> pd.DataFrame:
        """
        Load data from a Streamlit UploadedFile or any file-like buffer.
        """
        name = uploaded_file.name
        ext = os.path.splitext(name)[-1].lower()

        if ext == ".csv":
            df = pd.read_csv(uploaded_file, low_memory=False)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError(f"Unsupported format: {ext}. Use CSV or XLSX.")

        logger.info(f"Loaded from buffer '{name}': {len(df)} rows, {len(df.columns)} columns.")
        return df
