import pandas as pd


def extract_api_from_orange_book(products_df):
    """
    Robust API (chemical composition) extractor for FDA Orange Book PRODUCTS files.
    Handles all known FDA column name variants.
    """

    if products_df is None or products_df.empty:
        return "Unknown"

    # Normalize column names (strip spaces, preserve original)
    col_map = {c.strip().lower(): c for c in products_df.columns}
    row = products_df.iloc[0]

    # Ordered priority — FDA reality
    candidate_cols = [
        "ingredient",
        "activeingredient",
        "active_ingredient",
        "active ingredient",
    ]

    for key in candidate_cols:
        if key in col_map:
            val = row[col_map[key]]
            if pd.notna(val) and str(val).strip():
                return str(val).strip()

    return "Unknown"

import pandas as pd

def extract_chemical_profile(products_df):
    """
    FDA Orange Book–safe chemical profile extractor.
    Works with Ingredient + DF;Route format.
    """

    if products_df is None or products_df.empty:
        return {
            "api": "Unknown",
            "salt_form": "Unknown",
            "dosage_form": "Unknown",
            "route": "Unknown",
        }

    row = products_df.iloc[0]

    # ---------------------------
    # API (Ingredient)
    # ---------------------------
    api = "Unknown"
    if "Ingredient" in products_df.columns:
        val = row["Ingredient"]
        if pd.notna(val) and str(val).strip():
            api = str(val).strip()

    # ---------------------------
    # Dosage form + Route (DF;Route)
    # ---------------------------
    dosage_form = "Unknown"
    route = "Unknown"

    if "DF;Route" in products_df.columns:
        df_route = row["DF;Route"]
        if isinstance(df_route, str) and ";" in df_route:
            parts = df_route.split(";")
            dosage_form = parts[0].strip()
            route = parts[-1].strip()
        elif isinstance(df_route, str):
            dosage_form = df_route.strip()

    # ---------------------------
    # Salt detection (from API name)
    # ---------------------------
    salt_forms = [
        "hydrochloride", "sodium", "potassium", "mesylate",
        "phosphate", "acetate", "tartrate", "sulfate", "nitrate"
    ]

    salt_form = "Free base / not specified"
    api_lower = api.lower()

    for s in salt_forms:
        if s in api_lower:
            salt_form = s.capitalize()
            break

    return {
        "api": api,
        "salt_form": salt_form,
        "dosage_form": dosage_form,
        "route": route,
    }
