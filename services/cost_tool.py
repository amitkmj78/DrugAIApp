from typing import Dict


def formulation_cost_estimate(drug, route: str, dosage_form: str) -> Dict[str, any] :
    """
    Detailed CMC / formulation cost estimation (USD millions).
    Intended for US IND / ANDA / 505(b)(2) planning.
    """

    # ----------------------------
    # Base CMC ranges by route (USD M)
    # ----------------------------
    base = {
        "oral": (3.0, 8.0),
        "topical": (4.0, 10.0),
        "injectable": (8.0, 18.0),
        "inhaled": (12.0, 30.0),
    }

    route_key = route.lower()
    low, high = base.get(route_key, (5.0, 12.0))

    # ----------------------------
    # Complexity multipliers
    # ----------------------------
    df = dosage_form.lower()
    multiplier = 1.0
    complexity_flags = []

    if "extended" in df or "controlled" in df or "modified" in df:
        multiplier *= 1.3
        complexity_flags.append("Modified / extended release")

    if "lyoph" in df or "freeze-dried" in df:
        multiplier *= 1.5
        complexity_flags.append("Lyophilized formulation")

    if route_key == "injectable" and "sterile" in df:
        multiplier *= 1.4
        complexity_flags.append("Sterile manufacturing")

    if route_key == "inhaled":
        multiplier *= 1.3
        complexity_flags.append("Device + aerosol performance")

    # ----------------------------
    # Apply multiplier
    # ----------------------------
    low *= multiplier
    high *= multiplier

    # ----------------------------
    # Detailed cost buckets (informational)
    # ----------------------------
    breakdown = {
        "Pre-formulation & excipient compatibility": "0.8 – 2.0",
        "Process development & scale-up": "1.5 – 4.0",
        "Analytical method development & validation": "1.2 – 3.0",
        "ICH stability studies": "1.0 – 2.5",
        "CMC documentation & regulatory support": "0.6 – 1.5",
    }

    # ----------------------------
    # Cost drivers (dynamic)
    # ----------------------------
    drivers = [
        "API physicochemical complexity",
        "Formulation development & optimization",
        "Analytical and QC method development",
        "ICH stability studies (accelerated & long-term)",
        "Manufacturing process scale-up and tech transfer",
        "Primary packaging & compatibility studies",
    ]

    if complexity_flags:
        drivers.extend(complexity_flags)

    return {
        "low": round(low, 1),
        "high": round(high, 1),
        "drivers": drivers,
        "breakdown_usd_m": breakdown,
        "assumptions": [
            "Single dosage form",
            "US regulatory pathway",
            "CDMO-based development",
            "Excludes API synthesis cost",
            "Excludes clinical trial cost",
        ],
    }
