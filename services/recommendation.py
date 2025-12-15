# services/recommendation.py
from __future__ import annotations
from typing import Optional, Tuple
import pandas as pd


def _to_years_until(ege_date) -> Optional[float]:
    """Convert date → years until entry (None-safe)."""
    if ege_date is None:
        return None
    try:
        dt = pd.to_datetime(ege_date)
        days = (dt - pd.Timestamp.today()).days
        return max(days / 365.25, 0.0)
    except Exception:
        return None


def recommendation_flag(
    *,
    # -------------------------
    # NEW / ranking-style inputs
    # -------------------------
    ege_years: Optional[float] = None,
    formulation_risk: str = "Unknown",   # Low | Medium | High | Unknown
    density: str = "Unknown",            # Low | Moderate | High | Unknown

    # -------------------------
    # BACKWARD-COMPAT inputs (app calls)
    # -------------------------
    ege_date=None,
    route: Optional[str] = None,
    competition: Optional[str] = None,
    cost: Optional[dict] = None,
) -> Tuple[str, str]:
    """
    Returns (flag, rationale)

    Supports:
    A) ranking mode:
       recommendation_flag(ege_years=..., formulation_risk=..., density=...)

    B) app mode:
       recommendation_flag(ege_date=..., route=..., competition=..., cost=...)
    """

    # -------------------------------------------------
    # Map legacy inputs → normalized inputs
    # -------------------------------------------------
    if ege_years is None and ege_date is not None:
        ege_years = _to_years_until(ege_date)

    if competition and density == "Unknown":
        c = str(competition).strip().lower()
        if c.startswith("low"):
            density = "Low"
        elif c.startswith("mod"):
            density = "Moderate"
        elif c.startswith("high"):
            density = "High"

    if route and formulation_risk == "Unknown":
        r = str(route).strip().lower()
        if r in {"oral", "topical"}:
            formulation_risk = "Low"
        elif r in {"injectable", "inhaled"}:
            formulation_risk = "High"
        else:
            formulation_risk = "Unknown"

    # Cost-based escalation (only upward, never downward)
    if cost and isinstance(cost, dict):
        try:
            high_cost = float(cost.get("high", 0))
            if high_cost >= 20 and formulation_risk == "Low":
                formulation_risk = "Medium"
        except Exception:
            pass

    # -------------------------------------------------
    # Guard rails
    # -------------------------------------------------
    if formulation_risk == "Unknown" or density == "Unknown":
        return (
            "Watch",
            "Incomplete formulation or competition data; further assessment required",
        )

    fr = formulation_risk.lower()
    den = density.lower()

    # No blockers = immediate opportunity
    if ege_years is None:
        ege_years = 0.0

    # -------------------------------------------------
    # GO
    # -------------------------------------------------
    if (
        ege_years <= 2
        and den in {"low", "moderate"}
        and fr in {"low", "medium"}
    ):
        return (
            "Go",
            "Near-term or open entry with manageable technical complexity and competition",
        )

    # High-value complex generic
    if (
        ege_years <= 3
        and den == "low"
        and fr == "high"
    ):
        return (
            "Go",
            "Low competition combined with complex formulation supports a defensible, high-value generic",
        )

    # -------------------------------------------------
    # WATCH
    # -------------------------------------------------
    if (
        ege_years <= 4
        or den == "moderate"
        or fr == "medium"
    ):
        return (
            "Watch",
            "Opportunity exists but timing, formulation complexity, or competition requires monitoring",
        )

    # -------------------------------------------------
    # AVOID
    # -------------------------------------------------
    return (
        "Avoid",
        "Late entry combined with high formulation complexity or crowded competitive landscape",
    )
