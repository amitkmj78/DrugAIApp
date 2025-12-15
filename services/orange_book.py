# services/orange_book.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import streamlit as st

DATA_DIR = Path("data/orange_book")

# ----------------------------
# Loaders (match YOUR schemas)
# ----------------------------

@st.cache_data(show_spinner=False)
def load_orange_book_products() -> pd.DataFrame:
    products = pd.read_csv(
        DATA_DIR / "products.csv",
        sep="~",
        dtype=str,
        engine="python",
    )

    products.columns = [c.strip() for c in products.columns]

    # Standardized fields
    products["DrugName"] = products["Trade_Name"].str.strip()
    products["Appl_No"] = products["Appl_No"].str.strip()
    products["Applicant"]= products["Applicant"].str.strip()
    products["Product_No"] = products["Product_No"].str.strip()
    products["Strength"] = products["Strength"].str.strip()
    products["Applicant"] = products["Applicant"].str.strip()

    # 🔑 SPLIT DF;Route safely
    if "DF;Route" in products.columns:
        split = products["DF;Route"].str.split(";", n=1, expand=True)
        products["Dosage_Form"] = split[0].str.strip()
        products["Route"] = split[1].str.strip() if split.shape[1] > 1 else ""
    else:
        products["Dosage_Form"] = ""
        products["Route"] = ""

    products["DrugName_norm"] = products["DrugName"].str.upper()

    return products


@st.cache_data(show_spinner=False)
def load_orange_book_patents() -> pd.DataFrame:
    patents = pd.read_csv(
        DATA_DIR / "patents.csv",
        sep="~",
        dtype=str,
        engine="python",
    )

    patents.columns = [c.strip() for c in patents.columns]

    patents["Appl_No"] = patents["Appl_No"].str.strip()
    patents["Product_No"] = patents["Product_No"].str.strip()
    patents["Patent_No"] = patents["Patent_No"].str.strip()

    # Normalize expiry date column
    patents["Patent_Expire_Date"] = patents["Patent_Expire_Date_Text"].str.strip()
    patents["Patent_No_norm"] = patents["Patent_No"].str.upper()

    return patents


@st.cache_data(show_spinner=False)
def load_orange_book_exclusivities() -> pd.DataFrame:
    exclus = pd.read_csv(
        DATA_DIR / "exclusivity.csv",
        sep="~",
        dtype=str,
        engine="python",
    )

    exclus.columns = [c.strip() for c in exclus.columns]

    exclus["Appl_No"] = exclus["Appl_No"].str.strip()
    exclus["Product_No"] = exclus["Product_No"].str.strip()
    exclus["Exclusivity_Code"] = exclus["Exclusivity_Code"].str.strip()
    exclus["Exclusivity_Date"] = exclus["Exclusivity_Date"].str.strip()

    return exclus


@st.cache_data(show_spinner=False)
def load_orange_book_full() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        load_orange_book_products(),
        load_orange_book_patents(),
        load_orange_book_exclusivities(),
    )


# -----------------------------
# Dropdown helpers
# -----------------------------

@st.cache_data(show_spinner=False)
def get_drug_dropdown_list(limit: int = 5000) -> List[str]:
    products = load_orange_book_products()

    drugs = (
        products["DrugName"]
        .dropna()
        .str.strip()
        .str.title()
        .unique()
        .tolist()
    )

    drugs.sort()
    return drugs[:limit]


def get_patents_for_drug(drug_name: str) -> List[str]:
    """
    Return patent numbers associated with the selected drug
    using FDA-correct Appl_No linkage.
    """
    if not drug_name:
        return []

    products = load_orange_book_products()
    patents = load_orange_book_patents()

    key = drug_name.strip().upper()

    # 🔹 Match by Trade Name OR Ingredient (FDA reality)
    matched_products = products[
        products["DrugName_norm"].str.contains(key, na=False, regex=False)
        |
        (products["Ingredient"].str.upper().str.contains(key, na=False))
    ]

    if matched_products.empty:
        return []

    # 🔹 Normalize Appl_No on BOTH sides (critical)
    appl_nos = (
        matched_products["Appl_No"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.zfill(6)     # FDA standard
        .unique()
    )

    patents_norm = patents.copy()
    patents_norm["Appl_No"] = (
        patents_norm["Appl_No"]
        .astype(str)
        .str.strip()
        .str.zfill(6)
    )

    matched_patents = patents_norm[
        patents_norm["Appl_No"].isin(appl_nos)
    ]

    if matched_patents.empty:
        return []

    patent_list = (
        matched_patents["Patent_No"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    patent_list.sort()
    return patent_list


@st.cache_data(show_spinner=False)
def get_all_patent_dropdown_list(limit: int = 20000) -> List[str]:
    patents = load_orange_book_patents()

    pats = (
        patents["Patent_No"]
        .dropna()
        .unique()
        .tolist()
    )

    pats.sort()
    return pats[:limit]
# -----------------------------
# Lookups
# -----------------------------

def lookup_by_drug(drug_name: str):
    if not drug_name:
        return None

    products = load_orange_book_products()
    patents = load_orange_book_patents()
    exclus = load_orange_book_exclusivities()

    key = drug_name.strip().upper()

    prod = products[
        products["DrugName_norm"].str.contains(key, na=False, regex=False)

    ]

    if prod.empty:
        return None

    appl_nos = prod["Appl_No"].unique()

    pat = patents[patents["Appl_No"].isin(appl_nos)]
    exc = exclus[exclus["Appl_No"].isin(appl_nos)]

    return {
        "products": prod,
        "patents": pat,
        "exclusivities": exc,
    }


def lookup_by_patent(patent_no: str) -> Optional[Dict[str, pd.DataFrame]]:
    if not patent_no:
        return None

    products, patents, exclus = load_orange_book_full()

    key = patent_no.strip().upper()

    pat = patents[
        patents["Patent_No_norm"] == key
    ]

    if pat.empty:
        return None

    appl_nos = pat["Appl_No"].unique()

    prod = products[products["Appl_No"].isin(appl_nos)]
    exc = exclus[exclus["Appl_No"].isin(appl_nos)]

    return {
        "products": prod,
        "patents": pat,
        "exclusivities": exc,
    }


# -----------------------------
# Optional wide join
# -----------------------------

def join_products_patents_exclus(
    products: pd.DataFrame,
    patents: pd.DataFrame,
    exclus: pd.DataFrame,
) -> pd.DataFrame:
    for df in (products, patents, exclus):
        if "Appl_No" not in df.columns:
            df["Appl_No"] = ""
        if "Product_No" not in df.columns:
            df["Product_No"] = ""

    out = products.merge(
        patents,
        on=["Appl_No", "Product_No"],
        how="left",
        suffixes=("", "_pat"),
    )

    out = out.merge(
        exclus,
        on=["Appl_No", "Product_No"],
        how="left",
        suffixes=("", "_exc"),
    )

    return out
