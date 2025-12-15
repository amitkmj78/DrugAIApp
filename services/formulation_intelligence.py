from typing import Dict
import pandas as pd


# -----------------------------
# Formulation inference (SAFE)
# -----------------------------
from typing import Dict
import pandas as pd


from typing import Dict
import pandas as pd


def infer_formulation_type(products_df: pd.DataFrame) -> Dict[str, str]:
    """
    Infer formulation complexity from Orange Book Route + Dosage Form
    (Schema-safe, upload-safe)
    """

    if products_df is None or products_df.empty:
        return _unknown()

    df = products_df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # --- Safe column resolution ---
    route = _safe_first_any(df, [
        "route",
        "route_of_administration",
        "route_desc",
    ])

    dosage = _safe_first_any(df, [
        "dosage_form",
        "dosageform",
        "dosage_form_desc",
    ])

    if not route or not dosage:
        return _unknown(route, dosage)

    route_u = route.upper()
    dosage_u = dosage.upper()

    # Injectable
    if "INJECT" in route_u:
        if any(k in dosage_u for k in ["LIPOSOME", "DEPOT", "SUSPENSION", "LYOPH"]):
            return _complex("Injectable – Complex")
        return _complex("Injectable – Standard")

    # Inhalation
    if "INHAL" in route_u:
        return _complex("Inhalation")

    # Topical
    if "TOPICAL" in route_u:
        if any(k in dosage_u for k in ["FOAM", "AEROSOL"]):
            return _medium("Topical – Complex")
        return _simple("Topical – Simple")

    # Oral
    if "ORAL" in route_u:
        if any(k in dosage_u for k in ["EXTENDED", "CONTROLLED", "ER", "CR"]):
            return _medium("Oral – Modified Release")
        return _simple("Oral – Immediate Release")

    return {
        "route": route,
        "dosage_form": dosage,
        "formulation_type": "Other",
        "risk_level": "Medium",
    }
def _safe_first_any(df, candidates):
    for col in candidates:
        if col in df.columns:
            val = df[col].iloc[0]
            if val is not None:
                s = str(val).strip()
                if s:
                    return s
    return None


def _unknown(route=None, dosage=None):
    return {
        "route": route or "Unknown",
        "dosage_form": dosage or "Unknown",
        "formulation_type": "Unknown",
        "risk_level": "Unknown",
    }

# -----------------------------
# Risk helpers
# -----------------------------
def _simple(label: str) -> Dict[str, str]:
    return {
        "route": label.split(" – ")[0],
        "dosage_form": label,
        "formulation_type": label,
        "risk_level": "Low",
    }


def _medium(label: str) -> Dict[str, str]:
    return {
        "route": label.split(" – ")[0],
        "dosage_form": label,
        "formulation_type": label,
        "risk_level": "Medium",
    }


def _complex(label: str) -> Dict[str, str]:
    return {
        "route": label.split(" – ")[0],
        "dosage_form": label,
        "formulation_type": label,
        "risk_level": "High",
    }


def _unknown() -> Dict[str, str]:
    return {
        "route": "Unknown",
        "dosage_form": "Unknown",
        "formulation_type": "Unknown",
        "risk_level": "Unknown",
    }


# -----------------------------
# Safe column resolver
# -----------------------------
def _safe_first_any(df: pd.DataFrame, candidates: list[str]):
    for col in candidates:
        if col in df.columns:
            val = df[col].iloc[0]
            if pd.notna(val):
                s = str(val).strip()
                if s:
                    return s
    return None


# -----------------------------
# High-value complex flag
# -----------------------------
def is_high_value_complex(
    formulation_risk: str,
    density: str,
    ege_years: int | None,
) -> bool:
    """
    Complex + low competition + near EGE = high value
    """
    if formulation_risk == "High" and density in ["Low", "Medium"]:
        if ege_years is None or ege_years <= 3:
            return True
    return False
