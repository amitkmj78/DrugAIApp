import uuid
import pandas as pd
import streamlit as st

from services.chemical_profile import extract_chemical_profile
from services.extract_chemical_profile import extract_api_from_orange_book
from services.overview_service import build_executive_overview
from services.cost_tool import formulation_cost_estimate
from services.llm_setup import init_llms
from services.generic_entry import earliest_generic_entry
from services.recommendation import recommendation_flag
from services.competition import competitive_density_score
from services.formulation_intelligence import infer_formulation_type, is_high_value_complex

from services.orange_book import (
    lookup_by_drug,
    lookup_by_patent,
    get_drug_dropdown_list,
    get_patents_for_drug,
    load_orange_book_products,
    load_orange_book_patents,
    load_orange_book_exclusivities,
)

from services.market_insights import (
    find_all_generic_drugs,
    find_expiring_patents,
)

from services.opportunities import rank_top_orange_book_opportunities


# -------------------------------------------------
# Meta-agent import (optional; must NOT crash app)
# -------------------------------------------------
try:
    from Agent.meta_agent import build_agent
except Exception:
    build_agent = None


# -------------------------------------------------
# Page setup
# -------------------------------------------------
st.set_page_config(page_title="US Drug Formulation & Patent AI", layout="wide")
st.title("🧪 US Drug Formulation Cost & Patent Outlook")
st.caption("Estimates only • Not legal or financial advice")


# -------------------------------------------------
# Session state defaults
# -------------------------------------------------
st.session_state.setdefault("selected_drug", "")
st.session_state.setdefault("selected_patent", "")
st.session_state.setdefault("run_id", None)
st.session_state.setdefault("ai_summary", None)

st.session_state.setdefault("route", None)
st.session_state.setdefault("dosage_form", None)
st.session_state.setdefault("cost", None)

st.session_state.setdefault("months_horizon", 12)

# Meta-agent cache
st.session_state.setdefault("meta_agent", None)
st.session_state.setdefault("meta_agent_model", None)

# EGE table cache key in session (so we can avoid forced compute at startup)
st.session_state.setdefault("ege_master_df", pd.DataFrame())


def on_drug_change():
    st.session_state.selected_patent = ""
    st.session_state.run_id = None
    st.session_state.ai_summary = None
    st.session_state.route = None
    st.session_state.dosage_form = None
    st.session_state.cost = None


# -------------------------------------------------
# Load LLMs
# -------------------------------------------------
llm_openai, llm_groq, llm_ollama, llm_labels = init_llms()
if not llm_labels:
    st.error("No LLMs available.")
    st.stop()

model_choice = st.sidebar.selectbox("AI Model", llm_labels)

if model_choice.startswith("OpenAI"):
    llm = llm_openai
elif model_choice.startswith("Groq"):
    llm = llm_groq
else:
    llm = llm_ollama


# -------------------------------------------------
# Build/Rebuild Meta-Agent when model changes
# -------------------------------------------------
if build_agent is not None:
    if (
        st.session_state.meta_agent is None
        or st.session_state.meta_agent_model != model_choice
    ):
        try:
            st.session_state.meta_agent = build_agent(llm)
            st.session_state.meta_agent_model = model_choice
        except Exception as e:
            st.session_state.meta_agent = None
            st.session_state.meta_agent_model = None
            st.warning(f"Meta-agent not available: {e}")


# -------------------------------------------------
# Sidebar: Selection & Analysis Controls
# -------------------------------------------------
st.sidebar.subheader("Selection")

drug_list = get_drug_dropdown_list()
st.sidebar.selectbox(
    "Drug (FDA Orange Book)",
    [""] + drug_list,
    key="selected_drug",
    on_change=on_drug_change,
)

patent_options = (
    get_patents_for_drug(st.session_state.selected_drug)
    if st.session_state.selected_drug
    else []
)

st.sidebar.selectbox(
    "Patent (optional)",
    [""] + patent_options,
    key="selected_patent",
)

# -------------------------------------------------
# Formulation inputs (used by Analyze)
# -------------------------------------------------
st.sidebar.subheader("Formulation Inputs")

route_in = st.sidebar.selectbox(
    "Route",
    ["Oral", "Injectable", "Topical", "Inhaled"],
)

dosage_form_in = st.sidebar.text_input(
    "Dosage form / notes",
    placeholder="e.g., sterile injectable, extended-release tablet",
)

# -------------------------------------------------
# Analyze button
# -------------------------------------------------
analyze_clicked = st.sidebar.button(
    "🔍 Analyze",
    type="primary",
    disabled=not bool(st.session_state.selected_drug),
)

if analyze_clicked:
    st.session_state.route = route_in
    st.session_state.dosage_form = dosage_form_in

    st.session_state.cost = formulation_cost_estimate(
        st.session_state.selected_drug,
        route_in,
        dosage_form_in,
    )

    st.session_state.run_id = str(uuid.uuid4())
    st.session_state.ai_summary = None


selected_drug = st.session_state.selected_drug
selected_patent = st.session_state.selected_patent

# -------------------------------------------------
# Orange Book data for selected drug/patent
# -------------------------------------------------
ob_drug = lookup_by_drug(selected_drug) if selected_drug else None
ob_patent = lookup_by_patent(selected_patent) if selected_patent else None
ob_data = ob_patent or ob_drug  # may be None

# -------------------------------------------------
# Load Strategy datasets
# -------------------------------------------------
products = load_orange_book_products()
patents = load_orange_book_patents()
exclus = load_orange_book_exclusivities()

generic_df = find_all_generic_drugs(products, patents, exclus)
expiring_df = pd.DataFrame(find_expiring_patents(patents, st.session_state.months_horizon))


# -------------------------------------------------
# EGE builder (cached) — IMPORTANT: no DataFrame args
# -------------------------------------------------
@st.cache_data(show_spinner=False)
def build_ege_table_cached(max_drugs: int = 800) -> pd.DataFrame:
    """
    Builds EGE table using lookup_by_drug() + earliest_generic_entry().
    Cached with stable arguments (ints only) to avoid infinite recompute.

    max_drugs prevents UI freeze for huge datasets.
    """
    rows = []
    today = pd.Timestamp.today()

    products_local = load_orange_book_products()
    drug_names = products_local["DrugName"].dropna().unique().tolist()

    # Bound runtime
    drug_names = drug_names[:max_drugs]

    for drug in drug_names:
        ob = lookup_by_drug(drug)
        if not ob:
            continue

        ege_info = earliest_generic_entry(ob)
        ege_date = ege_info.get("earliest_date") if ege_info else None

        years_to_entry = (
            round((ege_date - today).days / 365, 1)
            if ege_date else 0.0
        )

        rows.append({
            "Drug": drug,
            "EGE Date": ege_date.date() if ege_date else "Open",
            "Years to Entry": years_to_entry,
            "Status": "Open" if ege_date is None else "Blocked",
        })

    return pd.DataFrame(rows)


# -------------------------------------------------
# Tabs
# -------------------------------------------------
overview_tab, ege_tab, strategy_tab, ai_tab = st.tabs(
    ["🏠 Overview", "⏳ Generic Entry (EGE)", "📊 Market Strategy", "🧠 AI Analysis"]
)

# =================================================
# OVERVIEW TAB
# =================================================
with overview_tab:
    st.subheader("Executive Overview")

    if not selected_drug:
        st.info("Select a drug from the sidebar to see executive summary signals.")
        st.stop()

    if not ob_data or ob_data.get("products") is None:
        st.error("Orange Book data not available for selected drug.")
        st.stop()

    try:
        overview = build_executive_overview(
            drug_name=selected_drug,
            route=st.session_state.get("route"),
            ob_data=ob_data,
            agent=st.session_state.get("meta_agent"),
        )
    except Exception as e:
        st.error(f"Failed to build executive overview: {e}")
        st.stop()

    formulation = infer_formulation_type(ob_data["products"]) if ob_data.get("products") is not None else {
        "formulation_type": "Unknown",
        "risk_level": "Unknown",
    }

    comp_count, comp_level = competitive_density_score(ob_data) if ob_data else (0, "Unknown")

    ege_date = None
    ege_years = None
    ege_info = earliest_generic_entry(ob_data) if ob_data else None
    if ege_info and ege_info.get("earliest_date") is not None:
        ege_date = ege_info["earliest_date"]
        ege_years = max(0.0, (ege_date - pd.Timestamp.today()).days / 365.0)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Selected Drug", selected_drug)
    k2.metric("Formulation", formulation.get("formulation_type", "Unknown"))
    k3.metric("Formulation Risk", formulation.get("risk_level", "Unknown"))

    cost = st.session_state.get("cost")
    if cost:
        k4.metric("Est. CMC Cost", f"${cost['low']}–{cost['high']}M")
    else:
        k4.metric("Est. CMC Cost", "—")

    k5.metric("Competition", f"{comp_level} ({comp_count})")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.write("### Summary")
        st.write(f"**Drug Class:** {overview.get('drug_class', '—')}")
        st.write(f"**Salt / Form:** {overview.get('salt_or_form', '—')}")
        st.write(f"**Dosage Form:** {overview.get('dosage_form', '—')}")
        st.write(f"**Route:** {overview.get('route', '—')}")

    with col2:
        st.write("### Regulatory (FDA)")
        reg = overview.get("regulatory", {}) or {}
        st.write(f"**Application Type:** {reg.get('application_type', '—')}")
        st.write(f"**Application No:** {reg.get('application_number', '—')}")

        if overview.get("risk_signals"):
            st.write("### Risk Signals")
            for r in overview["risk_signals"]:
                st.warning(r)

    with st.expander("Data Sources & Provenance"):
        st.json(overview.get("data_sources", {}))

    st.markdown("### 🧬 Chemical Composition")

    api_name = "Unknown"
    chem = None
    if ob_data and ob_data.get("products") is not None:
        api_name = extract_api_from_orange_book(ob_data["products"])
        chem = extract_chemical_profile(ob_data["products"])

    if chem:
        st.write(f"**API:** {api_name}")
        st.write(f"**Salt/Form:** {chem.get('Salt / Form', 'Unknown')}")
        st.write(f"**Strength:** {chem.get('Strength', 'Unknown')}")
        st.write(f"**Dosage Form:** {chem.get('Dosage Form', 'Unknown')}")
        st.write(f"**Route:** {chem.get('Route', 'Unknown')}")
    else:
        st.write("Chemical composition unavailable.")

    flag, rationale = recommendation_flag(
        ege_years=ege_years,
        formulation_risk=formulation.get("risk_level"),
        density=comp_level,
        route=st.session_state.get("route"),
        cost=cost,
        competition=comp_level,
    )

    st.markdown("### 🚦 Recommendation")
    if flag == "Go":
        st.success(f"🟢 GO — {rationale}")
    elif flag == "Watch":
        st.warning(f"🟡 WATCH — {rationale}")
    else:
        st.error(f"🔴 AVOID — {rationale}")

    if is_high_value_complex(
        formulation.get("risk_level"),
        comp_level,
        ege_years,
    ):
        st.info("💎 **High-Value Complex Generic Opportunity Identified**")


# =================================================
# EGE TAB
# =================================================
with ege_tab:
    st.subheader("⏳ Earliest Generic Entry (EGE) Dashboard")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Products", len(products))
    col2.metric("Generic-Ready Now", len(generic_df))
    col3.metric("Expiring ≤ 12 months", len(expiring_df))
    col4.metric("Tracked Opportunities", max(len(products) - len(generic_df), 0))

    st.divider()

    st.markdown("### 🔍 Selected Drug – EGE Detail")
    if not ob_data:
        st.info("Select a drug or patent from the sidebar to see EGE details.")
    else:
        ege_info = earliest_generic_entry(ob_data)
        ege_date = ege_info.get("earliest_date") if ege_info else None

        if ege_date:
            st.metric("Earliest Generic Entry", ege_date.strftime("%B %d, %Y"))
        else:
            st.success("No Orange Book blockers — generic eligible now")

        with st.expander("Blocking Patents & Exclusivities"):
            if ob_data.get("patents") is not None and not ob_data["patents"].empty:
                st.dataframe(ob_data["patents"], use_container_width=True)
            if ob_data.get("exclusivities") is not None and not ob_data["exclusivities"].empty:
                st.dataframe(ob_data["exclusivities"], use_container_width=True)

    st.divider()
    st.markdown("### 📅 Upcoming Generic Entry Opportunities")

    # Manual build so app never blocks on startup
    left, right = st.columns([1, 3])
    max_drugs = left.number_input("Max drugs to scan", min_value=100, max_value=5000, value=800, step=100)

    if left.button("⚡ Build / Refresh EGE Table", use_container_width=True):
        with st.spinner("Precomputing Earliest Generic Entry table…"):
            st.session_state.ege_master_df = build_ege_table_cached(int(max_drugs))

    ege_master_df = st.session_state.ege_master_df

    if ege_master_df is None or ege_master_df.empty:
        st.info("Click **Build / Refresh EGE Table** to generate the opportunity table.")
    else:
        f1, f2 = st.columns(2)
        max_years = f1.slider("Max Years to Entry", 0, 6, 3)
        status_filter = f2.multiselect("Status", ["Open", "Blocked"], default=["Open", "Blocked"])

        filtered_df = (
            ege_master_df[
                (ege_master_df["Years to Entry"] <= max_years)
                & (ege_master_df["Status"].isin(status_filter))
            ]
            .sort_values("Years to Entry")
        )

        st.dataframe(filtered_df, use_container_width=True, height=500)

    st.caption(
        "EGE = Earliest date a generic could legally launch based on Orange Book–listed "
        "patents and exclusivities only. Unlisted IP not assessed."
    )


# =================================================
# STRATEGY TAB
# =================================================
with strategy_tab:
    st.subheader("📊 Market Strategy")

    st.markdown("### 🟢 All Generic-Ready Drugs (No listed blockers)")
    st.metric("Generic-ready products", len(generic_df))
    st.dataframe(generic_df, use_container_width=True, height=450)

    st.markdown("### ⏱ Patents Expiring Soon")
    months_new = st.slider("Months ahead", 1, 48, st.session_state.months_horizon)
    if months_new != st.session_state.months_horizon:
        st.session_state.months_horizon = months_new

    expiring_df2 = pd.DataFrame(find_expiring_patents(patents, st.session_state.months_horizon))
    st.metric("Expiring patents", len(expiring_df2))
    st.dataframe(expiring_df2, use_container_width=True, height=450)

    st.divider()

    st.subheader("🏆 Top 20 Orange Book Opportunities (Auto-ranked)")
    if st.button("🔄 Refresh Top 20 Ranking", use_container_width=True):
        st.cache_data.clear()

    top20 = rank_top_orange_book_opportunities(products, patents, exclus, top_n=20)
    if top20.empty:
        st.info("No opportunities found (check Orange Book data load / columns).")
    else:
        st.dataframe(top20, use_container_width=True, height=650)
        st.caption("Scoring is conservative and based on Orange Book listed IP only (not unlisted patents).")


# =================================================
# AI ANALYSIS TAB
# =================================================
with ai_tab:
    st.subheader("🧠 AI Market Intelligence")

    if st.session_state.run_id is None or st.session_state.cost is None:
        st.info("Run Drug Analysis first (Analyze button) to generate AI summary.")
    else:
        expiring_df_now = pd.DataFrame(find_expiring_patents(patents, st.session_state.months_horizon))

        if st.session_state.ai_summary is None:
            top_generics = (
                generic_df.head(10)["DrugName"].astype(str).tolist()
                if not generic_df.empty and "DrugName" in generic_df.columns
                else []
            )
            expiring_sample = expiring_df_now.head(10).to_dict(orient="records") if not expiring_df_now.empty else []

            prompt = f"""
You are a US pharmaceutical strategy analyst.

Selected drug: {selected_drug}
Route: {st.session_state.route}
Dosage form: {st.session_state.dosage_form}
Estimated CMC cost: ${st.session_state.cost['low']}–${st.session_state.cost['high']}M

Market signals:
- Generic-ready products (count): {len(generic_df)}
- Sample generic-ready drug names: {top_generics}

- Patents expiring within {st.session_state.months_horizon} months (count): {len(expiring_df_now)}
- Sample expiring patents: {expiring_sample}

Write a concise executive summary:
1) What the opportunity is
2) Key risks (IP + technical)
3) What to prioritize next

Rules:
- Do NOT hallucinate patent dates.
- Do NOT give legal advice.
"""

            with st.spinner("Running AI analysis (one-time per Analyze)..."):
                st.session_state.ai_summary = llm.invoke(prompt).content

        st.write(st.session_state.ai_summary)
