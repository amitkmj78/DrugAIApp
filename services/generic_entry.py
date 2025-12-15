from datetime import datetime
import pandas as pd


def _parse_date_safe(date_str: str):
    """Parse FDA date strings safely."""
    if not date_str or pd.isna(date_str):
        return None

    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%b %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            continue

    return None


def earliest_generic_entry(ob_data: dict):
    """
    Calculate earliest generic entry date using
    Orange Book patents + exclusivities.

    Returns:
        {
            "earliest_date": datetime | None,
            "drivers": list[str],
            "patent_blockers": DataFrame,
            "exclusivity_blockers": DataFrame,
        }
    """
    if not ob_data:
        return None

    patents = ob_data.get("patents")
    exclus = ob_data.get("exclusivities")

    patent_dates = []
    excl_dates = []

    # ----------------------------
    # PATENT BLOCKERS
    # ----------------------------
    if patents is not None and not patents.empty:
        for _, row in patents.iterrows():
            d = _parse_date_safe(row.get("Patent_Expire_Date"))
            if d:
                patent_dates.append(d)

    # ----------------------------
    # EXCLUSIVITY BLOCKERS
    # ----------------------------
    if exclus is not None and not exclus.empty:
        for _, row in exclus.iterrows():
            d = _parse_date_safe(row.get("Exclusivity_Date"))
            if d:
                excl_dates.append(d)

    all_blockers = patent_dates + excl_dates

    if not all_blockers:
        return {
            "earliest_date": None,
            "drivers": ["No listed patents or exclusivities"],
            "patent_blockers": patents,
            "exclusivity_blockers": exclus,
        }

    ege = max(all_blockers)

    drivers = []
    if patent_dates:
        drivers.append("Orange Book listed patents")
    if excl_dates:
        drivers.append("FDA regulatory exclusivities")

    return {
        "earliest_date": ege,
        "drivers": drivers,
        "patent_blockers": patents,
        "exclusivity_blockers": exclus,
    }



def _parse_date_safe(date_str: str):
    if not date_str or pd.isna(date_str):
        return None
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%b %Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except Exception:
            continue
    return None


def compute_ege_for_all(products: pd.DataFrame,
                        patents: pd.DataFrame,
                        exclusivities: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Earliest Generic Entry (EGE) for all Appl_No.
    Returns a DataFrame with one row per Appl_No (and DrugName).
    """

    # Normalize Appl_No (CRITICAL)
    for df in (products, patents, exclusivities):
        if "Appl_No" in df.columns:
            df["Appl_No"] = (
                df["Appl_No"].astype(str).str.strip().str.zfill(6)
            )

    rows = []

    appl_nos = products["Appl_No"].dropna().unique()

    for appl in appl_nos:
        prod_rows = products[products["Appl_No"] == appl]
        pat_rows = patents[patents["Appl_No"] == appl]
        exc_rows = exclusivities[exclusivities["Appl_No"] == appl]

        # ---- patent dates ----
        pat_dates = []
        for d in pat_rows.get("Patent_Expire_Date", []):
            dt = _parse_date_safe(d)
            if dt:
                pat_dates.append(dt)

        # ---- exclusivity dates ----
        exc_dates = []
        for d in exc_rows.get("Exclusivity_Date", []):
            dt = _parse_date_safe(d)
            if dt:
                exc_dates.append(dt)

        blockers = pat_dates + exc_dates

        ege = max(blockers) if blockers else None

        rows.append({
            "Appl_No": appl,
            "DrugName": prod_rows["DrugName"].iloc[0] if "DrugName" in prod_rows else "",
            "Latest_Patent_Expiry": max(pat_dates).date() if pat_dates else None,
            "Latest_Exclusivity_Expiry": max(exc_dates).date() if exc_dates else None,
            "Earliest_Generic_Entry": ege.date() if ege else None,
            "Patent_Count": len(pat_rows),
            "Exclusivity_Count": len(exc_rows),
        })

    return pd.DataFrame(rows)
