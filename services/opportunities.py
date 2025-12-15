# services/opportunities.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd

from services.orange_book import lookup_by_drug
from services.generic_entry import earliest_generic_entry
from services.competition import competitive_density_score
from services.recommendation import recommendation_flag


def _safe_upper(s: Any) -> str:
    return str(s).strip().upper() if s is not None else ""

def _safe_str(s: Any) -> str:
    return str(s).strip() if s is not None else ""

def _infer_route_from_products(prod: pd.DataFrame) -> str:
    """
    Tries to infer route from Orange Book row fields.
    Your file has "DF;Route" in the raw data; your normalized loader may map it.
    We try multiple variants.
    """
    if prod is None or prod.empty:
        return "Unknown"

    cols = {c.strip().lower(): c for c in prod.columns}

    # common normalized
    for k in ["route", "rte", "rte_name"]:
        if k in cols:
            v = prod.iloc[0][cols[k]]
            if pd.notna(v) and _safe_str(v):
                return _safe_str(v)

    # source sample: "DF;Route"
    for k in ["df;route", "df_route", "dosage_form;route"]:
        if k in cols:
            v = prod.iloc[0][cols[k]]
            if pd.notna(v) and _safe_str(v):
                # e.g. "AEROSOL, FOAM;RECTAL"
                txt = _safe_str(v)
                parts = [p.strip() for p in txt.split(";") if p.strip()]
                return parts[-1] if parts else txt

    return "Unknown"

def _infer_dosage_form_from_products(prod: pd.DataFrame) -> str:
    if prod is None or prod.empty:
        return "Unknown"

    cols = {c.strip().lower(): c for c in prod.columns}

    for k in ["dosage_form", "dosage form", "df"]:
        if k in cols:
            v = prod.iloc[0][cols[k]]
            if pd.notna(v) and _safe_str(v):
                return _safe_str(v)

    # source: DF;Route has dosage form in front
    for k in ["df;route", "df_route", "dosage_form;route"]:
        if k in cols:
            v = prod.iloc[0][cols[k]]
            if pd.notna(v) and _safe_str(v):
                txt = _safe_str(v)
                parts = [p.strip() for p in txt.split(";") if p.strip()]
                return parts[0] if parts else txt

    return "Unknown"

def infer_formulation_risk(route: str, dosage_form: str) -> str:
    """
    Low/Medium/High/Unknown heuristic.
    Tune as needed.
    """
    r = _safe_str(route).lower()
    df = _safe_str(dosage_form).lower()

    if r in ["unknown", ""]:
        return "Unknown"

    # baseline
    risk = "Medium"

    if r in ["oral"]:
        risk = "Low"
    elif r in ["topical", "rectal", "ophthalmic", "otic", "nasal"]:
        risk = "Medium"
    elif r in ["injectable", "intravenous", "subcutaneous", "intramuscular"]:
        risk = "High"
    elif r in ["inhalation", "inhaled", "pulmonary"]:
        risk = "High"

    # dosage form complexity bump
    complex_terms = ["extended", "controlled", "modified", "delayed", "er", "xr", "dr", "osmotic", "liposome"]
    sterile_terms = ["sterile", "injectable"]
    device_terms = ["inhaler", "device", "aerosol", "metered", "nebuli", "spray"]
    if any(t in df for t in complex_terms):
        risk = "High" if risk != "Unknown" else "Unknown"
    if any(t in df for t in sterile_terms):
        risk = "High" if risk != "Unknown" else "Unknown"
    if any(t in df for t in device_terms):
        risk = "High" if risk != "Unknown" else "Unknown"

    return risk

def _ege_years_from_ob(ob_data: Optional[dict]) -> Optional[float]:
    if not ob_data:
        return None
    info = earliest_generic_entry(ob_data)
    dt = info.get("earliest_date") if info else None
    if not dt:
        return None
    try:
        dt = pd.to_datetime(dt)
        return (dt - pd.Timestamp.today()).days / 365.25
    except Exception:
        return None

def _roi_and_margin_band(ege_years: Optional[float], density: str, formulation_risk: str) -> Tuple[float, str]:
    """
    Lightweight ROI score (0-100) + margin band (Low/Medium/High).
    This is a heuristic until you integrate market size & pricing.
    """
    den = density.lower() if density else "unknown"
    fr = formulation_risk.lower() if formulation_risk else "unknown"

    # Base ROI score
    score = 50.0

    # Timing: sooner is better
    if ege_years is None:
        score += 20
    else:
        if ege_years <= 1:
            score += 20
        elif ege_years <= 2:
            score += 12
        elif ege_years <= 3:
            score += 5
        elif ege_years <= 5:
            score -= 5
        else:
            score -= 15

    # Competition: low is better
    if den == "low":
        score += 15
    elif den == "moderate":
        score += 5
    elif den == "high":
        score -= 10

    # Complexity: high complexity can be good if competition low (defensible)
    if fr == "low":
        score += 5
    elif fr == "medium":
        score += 0
    elif fr == "high":
        score += 8 if den == "low" else -5

    # Clamp
    score = max(0.0, min(100.0, score))

    # Margin band heuristic
    if den == "low" and fr == "high":
        band = "High"
    elif den in ["low", "moderate"] and fr in ["low", "medium"]:
        band = "Medium"
    else:
        band = "Low"

    return score, band
def rank_top_orange_book_opportunities(
    products: pd.DataFrame,
    patents: pd.DataFrame,
    exclus: pd.DataFrame,
    top_n: int = 20,
    min_name_len: int = 2,
    max_drugs: int = 1500,   # ✅ HARD SAFETY CAP
) -> pd.DataFrame:
    """
    Portfolio-level ranking using ONLY Orange Book-derived signals + heuristics.
    Returns a DataFrame with top N opportunities and GO/WATCH/AVOID labels.
    """

    if products is None or products.empty:
        return pd.DataFrame()

    # -----------------------------------
    # Find drug name column (once)
    # -----------------------------------
    cols = {c.strip().lower(): c for c in products.columns}
    drug_col = cols.get("drugname") or cols.get("drug_name")

    if not drug_col:
        return pd.DataFrame()

    # -----------------------------------
    # Build bounded drug universe
    # -----------------------------------
    drug_series = (
        products[drug_col]
        .dropna()
        .astype(str)
        .str.strip()
    )

    drug_series = drug_series[drug_series.str.len() >= min_name_len]

    drugs = (
        drug_series
        .drop_duplicates()
        .head(max_drugs)   # ✅ CRITICAL FIX
        .tolist()
    )

    rows = []
    now = pd.Timestamp.utcnow()

    for i, drug in enumerate(drugs, start=1):
        # Defensive guard (extra safety)
        if i > max_drugs:
            break

        ob = lookup_by_drug(drug)
        if not ob:
            continue

        prod = ob.get("products")
        route = _infer_route_from_products(prod)
        dosage_form = _infer_dosage_form_from_products(prod)

        # Competition density
        comp_count, density = competitive_density_score(ob)

        # EGE
        ege_years = _ege_years_from_ob(ob)

        # Formulation risk
        formulation_risk = infer_formulation_risk(route, dosage_form)

        # ROI heuristic
        roi_score, margin_band = _roi_and_margin_band(
            ege_years, density, formulation_risk
        )

        # Recommendation
        flag, rationale = recommendation_flag(
            ege_years=ege_years,
            formulation_risk=formulation_risk,
            density=density,
        )

        rows.append({
            "Drug": drug,
            "Route (inferred)": route,
            "Dosage Form (inferred)": dosage_form,
            "EGE Years": None if ege_years is None else round(float(ege_years), 2),
            "Competition": f"{density} ({comp_count})" if density != "Unknown" else "Unknown",
            "Formulation Risk": formulation_risk,
            "ROI Score (0-100)": round(roi_score, 1),
            "Margin Band": margin_band,
            "Opportunity Score": round(roi_score, 1),
            "Recommendation": flag,
            "Rationale": rationale,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df = df.sort_values(
        by=["Opportunity Score", "ROI Score (0-100)"],
        ascending=[False, False],
        kind="mergesort",
    ).head(top_n)

    df.insert(0, "Rank", range(1, len(df) + 1))
    return df
