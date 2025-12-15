from datetime import date, timedelta
import pandas as pd

def find_generic_ready(products: pd.DataFrame, patents: pd.DataFrame, exclus: pd.DataFrame):
    """
    Returns list of drugs with no listed patents and no exclusivities.
    """

    # Normalize Appl_No formats
    products["Appl_No"] = products["Appl_No"].astype(str).str.strip().str.zfill(6)
    patents["Appl_No"] = patents["Appl_No"].astype(str).str.strip().str.zfill(6)
    exclus["Appl_No"] = exclus["Appl_No"].astype(str).str.strip().str.zfill(6)

    ready_list = []

    for appl in products["Appl_No"].unique():
        has_pat = not patents[patents["Appl_No"] == appl].empty
        has_exc = not exclus[exclus["Appl_No"] == appl].empty

        if not has_pat and not has_exc:
            # get a canonical drug name for display
            drug_names = products[products["Appl_No"] == appl]["DrugName"].unique().tolist()
            ready_list.append({"Appl_No": appl, "DrugName": drug_names})

    return ready_list


def find_expiring_patents(patents: pd.DataFrame, months: int = 12):
    """
    Returns patents expiring within the next `months` months.
    """

    today = date.today()
    horizon = today + timedelta(days=months * 30)

    exp_list = []

    for idx, row in patents.iterrows():
        dt = None
        try:
            dt = pd.to_datetime(row["Patent_Expire_Date"])
            dt = dt.date()
        except Exception:
            continue

        if today <= dt <= horizon:
            exp_list.append({
                "Appl_No": row["Appl_No"],
                "Patent_No": row["Patent_No"],
                "Expiry": dt,
                "Use_Code": row.get("Patent_Use_Code", "")
            })

    # sort soonest first
    return sorted(exp_list, key=lambda x: x["Expiry"])

import pandas as pd


def find_all_generic_drugs(
    products: pd.DataFrame,
    patents: pd.DataFrame,
    exclus: pd.DataFrame,
) -> pd.DataFrame:
    """
    Identify products with NO listed blocking patents or exclusivities.
    Uses FDA Appl_No linkage (robust to uploaded file schemas).
    """

    if products is None or products.empty:
        return pd.DataFrame()

    # -------------------------------------------------
    # Normalize columns defensively
    # -------------------------------------------------
    products = products.copy()
    products.columns = (
        products.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    patents = patents.copy()
    patents.columns = (
        patents.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    exclus = exclus.copy()
    exclus.columns = (
        exclus.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # -------------------------------------------------
    # Resolve Appl_No safely
    # -------------------------------------------------
    appl_col = None
    for c in ["appl_no", "application_number", "nda_number", "anda_number"]:
        if c in products.columns:
            appl_col = c
            break

    if appl_col is None:
        # Cannot evaluate generic readiness without Appl_No
        return pd.DataFrame()

    products["appl_no_norm"] = (
        products[appl_col]
        .astype(str)
        .str.strip()
        .str.zfill(6)
    )

    # -------------------------------------------------
    # Normalize patent + exclusivity Appl_No
    # -------------------------------------------------
    blocking_appls = set()

    if "appl_no" in patents.columns:
        blocking_appls.update(
            patents["appl_no"]
            .astype(str)
            .str.strip()
            .str.zfill(6)
            .dropna()
            .unique()
        )

    if "appl_no" in exclus.columns:
        blocking_appls.update(
            exclus["appl_no"]
            .astype(str)
            .str.strip()
            .str.zfill(6)
            .dropna()
            .unique()
        )

    # -------------------------------------------------
    # Generic-ready = NO blockers
    # -------------------------------------------------
    generic_df = products[
        ~products["appl_no_norm"].isin(blocking_appls)
    ].copy()

    # -------------------------------------------------
    # Friendly display columns
    # -------------------------------------------------
    name_cols = [c for c in ["drugname", "trade_name", "ingredient"] if c in generic_df.columns]
    if name_cols:
        generic_df["DrugName"] = generic_df[name_cols[0]].astype(str).str.strip()

    return generic_df.reset_index(drop=True)
