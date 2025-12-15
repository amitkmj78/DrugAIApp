from __future__ import annotations

import pandas as pd
from typing import Dict, Any
from io import BytesIO, StringIO


# -------------------------------------------------
# Column normalization (safe & reversible)
# -------------------------------------------------
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.replace("\n", " ", regex=False)
        .str.replace("/", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
        .str.lower()
    )
    return df


# -------------------------------------------------
# Read Excel OR CSV dynamically (Streamlit-safe)
# -------------------------------------------------
def read_file_dynamic(
    uploaded_file,
    *,
    normalize: bool = True,
    max_rows_preview: int = 1000,
    csv_delimiter: str = "~",
) -> Dict[str, Dict[str, Any]]:
    """
    Reads a Streamlit UploadedFile (Excel or CSV).

    Returns:
    {
        sheet_or_table_name: {
            'data': DataFrame (preview),
            'columns': list[str],
            'row_count': int
        }
    }
    """
    result: Dict[str, Dict[str, Any]] = {}

    if uploaded_file is None:
        return result

    filename = uploaded_file.name.lower()

    # =============================
    # CSV HANDLING
    # =============================
    if filename.endswith(".csv"):
        try:
            text = uploaded_file.read().decode("utf-8", errors="replace")
            df = pd.read_csv(
                StringIO(text),
                sep=csv_delimiter,
                dtype=str,
                engine="python",
            )

            if df.empty:
                return result

            if normalize:
                df = normalize_columns(df)

            result["CSV"] = {
                "data": df.head(max_rows_preview),
                "columns": list(df.columns),
                "row_count": len(df),
            }

        except Exception as e:
            result["CSV"] = {
                "error": str(e),
                "data": None,
                "columns": [],
                "row_count": 0,
            }

        return result

    # =============================
    # EXCEL HANDLING
    # =============================
    try:
        excel = pd.ExcelFile(uploaded_file)
    except Exception as e:
        return {
            "error": {
                "error": f"Unable to read file as Excel or CSV: {e}",
                "data": None,
                "columns": [],
                "row_count": 0,
            }
        }

    for sheet in excel.sheet_names:
        try:
            df = excel.parse(sheet, dtype=str)

            if df.empty:
                continue

            if normalize:
                df = normalize_columns(df)

            result[sheet] = {
                "data": df.head(max_rows_preview),
                "columns": list(df.columns),
                "row_count": len(df),
            }

        except Exception as e:
            result[sheet] = {
                "error": str(e),
                "data": None,
                "columns": [],
                "row_count": 0,
            }

    return result
