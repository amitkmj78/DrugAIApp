# services/competition.py
from __future__ import annotations
from typing import Tuple, Optional

def competitive_density_score(ob_data: Optional[dict]) -> Tuple[int, str]:
    """
    Returns: (competing_product_count, density_label)
    Uses the number of product rows as a simple proxy for competitive density.
    """
    if not ob_data or "products" not in ob_data or ob_data["products"] is None:
        return 0, "Unknown"

    df = ob_data["products"]
    try:
        n = int(len(df))
    except Exception:
        return 0, "Unknown"

    # heuristic thresholds (tune later)
    if n <= 2:
        return n, "Low"
    if n <= 6:
        return n, "Moderate"
    return n, "High"
