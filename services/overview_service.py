# services/overview_service.py
from __future__ import annotations
from typing import Dict, Any, Optional, List
import pandas as pd
from services.formulation_intelligence import infer_formulation_type

# Optional safe agent wrapper
try:
    from Agent.agent_service import call_agent_safe
except Exception:
    call_agent_safe = None


# ============================
# PUBLIC ENTRY POINT
# ============================
def build_executive_overview(
    drug_name: str,
    route: Optional[str],
    ob_data: Dict[str, Any],
    agent=None,
    
) -> Dict[str, Any]:
    """
    Builds a compliance-safe executive overview by combining:
    - FDA Orange Book (source of truth)
    - AI Agent (interpretation only, optional)
    """

    products = ob_data.get("products")
    if products is None or getattr(products, "empty", True):
        raise ValueError("Orange Book product data is required")

    # -------------------------------------------------
    # Normalize a WORKING COPY (never mutate source)
    # -------------------------------------------------
    prod = products.copy()
    prod.columns = (
        prod.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # -------------------------------------------------
    # 1) FDA-GROUNDED FIELDS (ROBUST)
    # -------------------------------------------------
    dosage_form = _safe_first_any(
        prod,
        ["dosage_form", "dosageform", "dosage_form_desc", "dosage_form_description"],
    )

    ingredient = _safe_first_any(
        prod,
        ["ingredient", "active_ingredient", "activeingredient"],
    )

    app_type = _safe_first_any(
        prod,
        ["appl_type", "application_type"],
    )

    app_no = _safe_first_any(
        prod,
        ["appl_no", "application_number", "nda_number", "anda_number"],
    )
    
# ----------------------------
# Company / Applicant Name (ROBUST)
# ----------------------------
    company_name = _safe_first_any(
    prod,
    [
        # FDA Orange Book (most common)
        "applicant_full_name",
        "applicant_name",
        "applicant",
        "labeler",
        "labeler_name",
        "firm_name",
        "sponsor",
        "holder",

        # Uploaded / vendor variants
        "company_name",
        "company",
        "manufacturer",
        "mfr_name",
    ],
)


    # Route: FDA first, then UI override
    route_from_ob = _safe_first_any(
        prod,
        ["route", "route_desc", "route_of_administration"],
    )

    final_route = route_from_ob or route or "Unknown"

    # -------------------------------------------------
    # 2) DETERMINISTIC FORMULATION
    # (use ORIGINAL df – preserves internal expectations)
    # -------------------------------------------------
    formulation = infer_formulation_type(products) or {}
    formulation_type = formulation.get("formulation_type") or "Unknown"

    # -------------------------------------------------
    # 3) AI AGENT (INTERPRETATION ONLY, SAFE)
    # -------------------------------------------------
    agent_insights: Dict[str, Any] = {}
    agent_context = {
    "drug_name": drug_name,
    "api": ingredient,                     # 🔑 REQUIRED
    "salt_or_form": formulation_type,
    "route": route,
    "dosage_form": dosage_form,
    "instruction": (
        "Classify the drug into a pharmacologic class "
        "(e.g., beta-lactam antibiotic, ACE inhibitor). "
        "Do NOT infer indications or regulatory claims."
    ),
}


    if agent is not None:
        if callable(call_agent_safe):
            try:
                agent_insights = call_agent_safe(agent, agent_context) or {}
            except Exception:
                agent_insights = {}
        else:
            try:
                from Agent.meta_agent import ask_meta_agent
                agent_insights = ask_meta_agent(agent, agent_context) or {}
            except Exception:
                agent_insights = {}

    # --- Drug class resolution (SAFE) ---
    drug_class = agent_insights.get("drug_class")

    # Hard fallback: derive from API string (NO hallucination)
    if not drug_class or drug_class == "Unknown":
        if ingredient:
            drug_class = ingredient.split()[0].title() + " class"
        else:
            drug_class = "Unknown"

        risk_flags = (
            agent_insights.get("risk_flags")
            or agent_insights.get("risk_signals")
            or []
        )

    # -------------------------------------------------
    # 4) MERGED OUTPUT (FDA FIRST)
    # -------------------------------------------------
    return {
        "drug": drug_name,
        "drug_class": drug_class,
        "salt_or_form": formulation_type,
        "dosage_form": dosage_form or "Unknown",
        "route": final_route,
        "regulatory": {
            "company_name": company_name,  # ✅ NEW
            "application_type": app_type or "Unknown",
            "application_number": app_no or "Unknown",
        
        },
        "risk_signals": risk_flags,
        "data_sources": {
            "drug_class": "AI Agent" if agent else "Unavailable",
            "salt_or_form": "FDA Orange Book + AI Interpretation",
            "dosage_form": "FDA Orange Book",
            "route": "FDA Orange Book",
            "regulatory": "FDA Orange Book",
            "risk_signals": "AI Agent" if agent else "Unavailable",
        },
    }


# ============================
# INTERNAL HELPERS
# ============================
def _safe_first_any(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """
    Return first non-empty value from the first matching column.
    df must already have normalized columns.
    """
    for col in candidates:
        if col in df.columns:
            val = df[col].iloc[0]
            if pd.isna(val):
                return None
            s = str(val).strip()
            if s:
                return s
    return None
