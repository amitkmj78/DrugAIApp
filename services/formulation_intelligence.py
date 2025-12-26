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

def compute_formulation_risk(formulation: dict, route: str | None = None) -> dict:
    """
    Returns formulation risk score and label based on complexity signals.
    Output:
      {
        "score": int (0–100),
        "level": "Low" | "Medium" | "High",
        "drivers": [list of strings]
      }
    """

    if not formulation:
        return {
            "score": 50,
            "level": "Medium",
            "drivers": ["Insufficient formulation data"],
        }

    score = 0
    drivers = []

    form_type = formulation.get("formulation_type", "").lower()
    risk_level = formulation.get("risk_level", "").lower()

    # -------------------------
    # Route-based risk
    # -------------------------
    if route:
        r = route.lower()
        if r in ["injectable", "inhaled"]:
            score += 35
            drivers.append(f"{route} delivery complexity")
        elif r == "topical":
            score += 20
            drivers.append("Topical formulation variability")
        elif r == "oral":
            score += 10

    # -------------------------
    # Dosage / formulation cues
    # -------------------------
    high_risk_terms = [
        "liposome", "depot", "suspension", "emulsion",
        "extended", "modified", "controlled", "complex",
        "lyophil", "nanoparticle", "device"
    ]

    for term in high_risk_terms:
        if term in form_type:
            score += 15
            drivers.append(f"Complex formulation: {term}")

    # -------------------------
    # Orange Book inferred risk
    # -------------------------
    if risk_level == "high":
        score += 30
        drivers.append("Orange Book formulation risk")
    elif risk_level == "medium":
        score += 15

    # -------------------------
    # Clamp + label
    # -------------------------
    score = min(score, 100)

    if score >= 65:
        level = "High"
    elif score >= 35:
        level = "Medium"
    else:
        level = "Low"

    return {
        "score": score,
        "level": level,
        "drivers": drivers,
    }
