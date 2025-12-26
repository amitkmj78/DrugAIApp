import uuid
import os
import pandas as pd
import streamlit as st
from datetime import datetime

from services.chemical_profile import extract_chemical_profile
from services.excel_loader import read_file_dynamic
from services.extract_chemical_profile import extract_api_from_orange_book
from services.overview_service import build_executive_overview
from services.cost_tool import formulation_cost_estimate
from services.llm_setup import init_llms
from services.generic_entry import earliest_generic_entry
from services.recommendation import recommendation_flag
from services.competition import competitive_density_score
from services.formulation_intelligence import compute_formulation_risk, infer_formulation_type, is_high_value_complex

from services.orange_book import (
    build_ege_table_cached,
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



# =====================================================
# Reload helper
# =====================================================
def reload_app_after_upload():
    st.cache_data.clear()
    st.cache_resource.clear()

    for key in [
        "selected_drug",
        "selected_patent",
        "selected_opportunity_drug",
        "ege_master_df",
        "top20_opportunities",
        "top20_computed",
        "ai_summary",
        "board_summary",
        "run_id",
    ]:
        st.session_state.pop(key, None)

    st.rerun()


# =====================================================
# Optional Meta-Agent
# =====================================================
try:
    from Agent.meta_agent import build_agent
except Exception:
    build_agent = None


# =====================================================
# Page setup
# =====================================================
st.set_page_config(page_title="Pharma Commercial Decision Engine", layout="wide")
st.title("🧪 Pharma Commercial Decision Engine")
st.caption("Orange Book–driven generic drug opportunity intelligence • Not legal or financial advice")


# =====================================================
# Session defaults
# =====================================================
DEFAULTS = {
    "selected_drug": "",
    "selected_patent": "",
    "selected_opportunity_drug": "",
    "run_id": None,
    "ai_summary": None,
    "board_summary": None,
    "route": None,
    "dosage_form": None,
    "cost": None,
    "months_horizon": 12,
    "meta_agent": None,
    "meta_agent_model": None,
    "ege_master_df": pd.DataFrame(),
}

for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

DEFAULTS.update({
    "next_plan_text": None,
    "next_plan_run_id": None,
    "next_plan_style": "Corporate BD / IC Memo",  # default
})


def on_drug_change():
    for k in ["selected_patent", "run_id", "ai_summary", "board_summary", "route", "dosage_form", "cost"]:
        st.session_state[k] = None if k != "selected_patent" else ""


# =====================================================
# Load LLMs
# =====================================================
llm_openai, llm_groq, llm_ollama, llm_labels = init_llms()
if not llm_labels:
    st.error("No LLMs available.")
    st.stop()

model_choice = st.sidebar.selectbox("AI Model", llm_labels, key="model_choice")

llm = (
    llm_openai if model_choice.startswith("OpenAI")
    else llm_groq if model_choice.startswith("Groq")
    else llm_ollama
)

if build_agent and (
    st.session_state.meta_agent is None
    or st.session_state.meta_agent_model != model_choice
):
    try:
        st.session_state.meta_agent = build_agent(llm)
        st.session_state.meta_agent_model = model_choice
    except Exception:
        st.session_state.meta_agent = None


# =====================================================
# Cached opportunity dropdown
# =====================================================
@st.cache_data(show_spinner=False)
def build_top_opportunity_dropdown(max_drugs=1500, top_n=1000):
    products = load_orange_book_products()
    patents = load_orange_book_patents()
    exclus = load_orange_book_exclusivities()

    ranked = rank_top_orange_book_opportunities(
        products=products,
        patents=patents,
        exclus=exclus,
        top_n=top_n,
        max_drugs=max_drugs,
    )

    if ranked is None or ranked.empty:
        return []

    col = "Ingredient" if "Ingredient" in ranked.columns else "Drug"
    return ranked[col].dropna().unique().tolist()


# =====================================================
# Sidebar — Selection
# =====================================================
st.sidebar.subheader("Selection Mode")

selection_mode = st.sidebar.radio(
    "Choose selection source",
    ["FDA Orange Book All", "🔥 Top Opportunities"],
    key="selection_mode",
)

st.sidebar.divider()

if selection_mode == "FDA Orange Book All":
    drug_list = get_drug_dropdown_list()
    st.sidebar.selectbox(
        "Drug (FDA Orange Book)",
        [""] + drug_list,
        key="selected_drug",
        on_change=on_drug_change,
    )
else:
    with st.spinner("Loading top opportunities…"):
        opp_list = build_top_opportunity_dropdown()

    st.sidebar.selectbox(
        "🔥 Top-1000 Opportunity Drugs",
        [""] + opp_list,
        key="selected_opportunity_drug",
    )

    if st.session_state.selected_opportunity_drug:
        if st.session_state.selected_drug != st.session_state.selected_opportunity_drug:
            st.session_state.selected_drug = st.session_state.selected_opportunity_drug
            on_drug_change()


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

# st.sidebar.subheader("Formulation Inputs")
# route_in = st.sidebar.selectbox("Route", ["Oral", "Injectable", "Topical", "Inhaled"], key="route_in")
# dosage_form_in = st.sidebar.text_input("Dosage form / notes", key="dosage_form_in")

if st.sidebar.button(
    "🔍 Analyze",
    type="primary",
    disabled=not bool(st.session_state.selected_drug),
    key="analyze_btn",
):
    #st.session_state.route = route_in
    #st.session_state.dosage_form = dosage_form_in
    st.session_state.cost = formulation_cost_estimate(
    st.session_state.selected_drug, st.session_state.route or "", st.session_state.dosage_form or ""
    )
    st.session_state.run_id = str(uuid.uuid4())
    st.session_state.ai_summary = None
    st.session_state.board_summary = None


# =====================================================
# Core data
# =====================================================
selected_drug = st.session_state.selected_drug

ob_data = (
    lookup_by_patent(st.session_state.selected_patent)
    if st.session_state.selected_patent
    else lookup_by_drug(selected_drug)
)

products = load_orange_book_products()
patents = load_orange_book_patents()
exclus = load_orange_book_exclusivities()

generic_df = find_all_generic_drugs(products, patents, exclus)
expiring_df = pd.DataFrame(find_expiring_patents(patents, st.session_state.months_horizon))
def build_next_level_plan_text(
    llm,
    style: str,
    drug: str,
    formulation_type: str,
    formulation_risk_level: str,
    formulation_risk_score: int | None,
    competition_level: str,
    competition_count: int | None,
    ege_years: float | None,
    cmc_cost: dict | None,
) -> str:
    """
    LLM-generated execution plan section. Returns markdown text.
    """

    ege_text = "Open now" if ege_years is None else f"{ege_years:.1f} years"
    cost_text = "Unknown" if not cmc_cost else f"${cmc_cost.get('low')}–${cmc_cost.get('high')}M"

    # Tone control
    style_map = {
        "VC Pitch": "VC pitch: concise, value-creation, milestone-driven, speed-focused.",
        "PE Diligence": "PE diligence: risk controls, cost certainty, execution gates, downside protection.",
        "Corporate BD / IC Memo": "Corporate BD / IC memo: strategic fit, regulatory path, operational readiness, partnership angles.",
    }
    style_instr = style_map.get(style, style_map["Corporate BD / IC Memo"])

    prompt = f"""
You are a US pharma commercialization strategy lead.

Write a section titled:
"Next-Level Execution Plan (Commercial-Scale Readiness)"

Audience style:
{style_instr}

Context (do NOT invent facts or numbers):
- Drug: {drug}
- Formulation type: {formulation_type}
- Formulation risk: {formulation_risk_level}{f" ({formulation_risk_score}/100)" if formulation_risk_score is not None else ""}
- Competition: {competition_level}{f" ({competition_count})" if competition_count is not None else ""}
- Earliest Generic Entry (EGE): {ege_text}
- Estimated CMC cost: {cost_text}

Required structure (use numbered headings 1–5):
1) Formulation stability & scale-up validation
2) Supply-chain lock-in & cost certainty
3) Market access & pricing optimization
4) Regulatory & exclusivity leverage (mention 180-day exclusivity only as feasibility evaluation, not a claim)
5) Rapid-launch operational plan

Constraints:
- No legal advice
- No fabricated dates, market sizes, or pricing numbers
- Keep it 120–200 words total
- Use crisp, executive language
Return markdown only (no code fences).
"""

    return llm.invoke(prompt).content.strip()

# =====================================================
# Tabs
# =====================================================
overview_tab, ege_tab, strategy_tab, ai_tab, data_upload = st.tabs(
    ["🏠 Executive Overview", "⏳ Generic Entry (EGE)", "📊 Strategy", "🧠 AI Analysis", "📂 Data Upload"]
)

# =====================================================
# OVERVIEW TAB
# =====================================================
with overview_tab:
    st.subheader("Executive Overview")

    # ----------------------------
    # Guards
    # ----------------------------
    if not selected_drug or not ob_data or ob_data.get("products") is None:
        st.info("Select a drug and click Analyze to view the executive overview.")
        st.stop()
    
    # ----------------------------
    # Executive overview (core)
    # ----------------------------
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

    # ----------------------------
    # Derived signals (compute ONCE)
    # ----------------------------
    formulation = infer_formulation_type(ob_data["products"]) or {
        "formulation_type": "Unknown",
        "risk_level": "Unknown",
    }
    # ----------------------------
    # Formulation Risk (computed)
    # ----------------------------
    formulation_risk = compute_formulation_risk(
        formulation=formulation,
        route=st.session_state.get("route"),
    )

    comp_count, comp_level = competitive_density_score(ob_data) if ob_data else (0, "Unknown")

    ege_info = earliest_generic_entry(ob_data)
    ege_years = None
    if ege_info and ege_info.get("earliest_date"):
        ege_years = max(
            0.0,
            (ege_info["earliest_date"] - pd.Timestamp.today()).days / 365.0,
        )

    cost = st.session_state.get("cost")

    # ----------------------------
    # KPI row
    # ----------------------------
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Drug", selected_drug)
    c2.metric("Formulation", formulation.get("formulation_type", "—"))
    c3.metric("Risk", formulation.get("risk_level", "—"))
    c4.metric(
        "CMC Cost",
        f"${cost['low']}–{cost['high']}M" if cost else "—",
    )
    c5.metric("Competition", f"{comp_level} ({comp_count})")
    st.divider()

    # ----------------------------
    # Summary + Regulatory
    # ----------------------------
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Summary")
        st.write(f"**Drug Class:** {overview.get('drug_class', '—')}")
        st.write(f"**Salt / Form:** {overview.get('salt_or_form', '—')}")
        st.write(f"**Dosage Form:** {overview.get('dosage_form', '—')}")
        st.write(f"**Route:** {overview.get('route', '—')}")
    
    with col2:
        st.markdown("### Regulatory (FDA)")
        reg = overview.get("regulatory", {}) or {}
        st.write(f"**Application Type:** {reg.get('application_type', '—')}")
        st.write(f"**Application No:** {reg.get('application_number', '—')}")
        st.write(f"**Company:** {reg.get('company_name', '—')}")  
        if overview.get("risk_signals"):
            st.markdown("### Risk Signals")
            for r in overview["risk_signals"]:
                st.warning(r)
   
    # ----------------------------
    # Chemical composition
    # ----------------------------
    st.markdown("### 🧬 Chemical Composition")

    api_name = "Unknown"
    chem = None
    if ob_data.get("products") is not None:
        api_name = extract_api_from_orange_book(ob_data["products"])
        chem = extract_chemical_profile(ob_data["products"])
    
    if chem:
        st.write(f"**API:** {api_name}")
        st.write(f"**Salt/Form:** {chem.get('Salt / Form', 'Unknown')}")
        strength = (
            chem.get("Strength")
            or chem.get("strength")
            or chem.get("strength_text")
            or chem.get("strength_desc")
            or "Unknown"
        )
        st.write(f"**Strength:** {strength}")
       
        st.write(f"**Dosage Form:** {chem.get('Dosage Form', 'Unknown')}")
        route_display = (
                chem.get("Route")
                or chem.get("route")
                or chem.get("route_of_administration")
                or st.session_state.get("route")
                or "Unknown"
            )
        st.write(f"**Route:** {route_display}")
    else:
        st.write("Chemical composition unavailable.")

    # ----------------------------
    # Recommendation (single call)
    # ----------------------------
    flag, rationale = recommendation_flag(
        ege_years=ege_years,
        formulation_risk=formulation.get("risk_level"),
        density=comp_level,
        route=st.session_state.get("route"),
        cost=cost,
        competition=comp_level,
    )

    st.markdown("### 🚦 Recommendation")
    {"Go": st.success, "Watch": st.warning, "Avoid": st.error}[flag](
        f"{flag.upper()} — {rationale}"
    )

    if is_high_value_complex(formulation.get("risk_level"), comp_level, ege_years):
        st.info("💎 **High-Value Complex Generic Opportunity Identified**")

# =================================================
# 🧾 Board Summary (3 sentences, cached)
# =================================================
    st.session_state.setdefault("board_summary", None)
    st.session_state.setdefault("board_summary_run_id", None)
    can_generate = bool(st.session_state.get("run_id"))
    if can_generate:
        st.markdown("### 🧾 Board Summary")
        # Reset ONLY when Analyze is clicked
        if st.session_state.board_summary_run_id != st.session_state.run_id:
            st.session_state.board_summary = None
            st.session_state.board_summary_run_id = st.session_state.run_id

        if st.session_state.board_summary is None:
            prompt = f"""
    Write exactly 3 sentences for a board of directors.

    Drug: {selected_drug}
    Formulation: {formulation['formulation_type']} ({formulation['risk_level']} risk)
    Competition: {comp_level}
    Earliest Generic Entry: {"Open now" if ege_years is None else f"{ege_years:.1f} years"}
    Estimated CMC Cost: {"Unknown" if not cost else f"${cost['low']}–${cost['high']}M"}

    Rules:
    - No legal advice
    - No invented numbers
    - Executive tone only
    """

            with st.spinner("Generating board summary…"):
                st.session_state.board_summary = llm.invoke(prompt).content.strip()

    st.write(st.session_state.board_summary or "—")

    # ==============================
    # INVESTOR SNAPSHOT (ALL AUDIENCES)
    # ==============================
    st.divider()
    st.markdown("### 🏦 Investor Pitch Snapshot")

    colL, colR = st.columns([2, 1])

    # ---------
    # Universal Snapshot (default)
    # ---------
    with colL:
        st.write(
            "This platform converts FDA Orange Book regulatory data into a ranked pipeline of "
            "high-confidence generic drug development opportunities. By integrating IP timing, "
            "formulation complexity, competitive intensity, and estimated CMC cost, it enables "
            "disciplined capital allocation and earlier identification of commercially viable programs."
        )

    with colR:
        st.metric("EGE", "Open" if ege_years is None else f"{ege_years:.1f}y")
        st.metric("Formulation Risk", formulation.get("risk_level"))
        st.metric("Competition", comp_level)

    # ---------
    # Audience-specific expansions
    # ---------
    # with st.expander("🎯 Audience-Specific Positioning"):
        
    #     st.markdown("#### 🟣 Venture Capital (Platform & Scale)")
    #     st.write(
    #         "We are building a scalable decision intelligence platform that transforms FDA Orange "
    #         "Book data into a repeatable pipeline of high-conviction generic drug opportunities. "
    #         "By combining IP timing, formulation risk, competitive dynamics, and cost modeling, "
    #         "the platform surfaces asymmetric upside earlier than traditional diligence processes—"
    #         "creating a defensible data moat for generic drug investing."
    #     )

    #     st.markdown("#### 🔵 Private Equity (Risk-Adjusted Returns)")
    #     st.write(
    #         "This platform functions as a risk-adjusted screening engine for generic drug investments, "
    #         "allowing sponsors to systematically evaluate ROI, development risk, and time-to-market. "
    #         "By eliminating low-quality opportunities early, it reduces capital leakage and improves "
    #         "probability-weighted returns across a diversified portfolio."
    #     )

    #     st.markdown("#### 🟢 Corporate BD / Pharma Strategy (Execution & Alignment)")
    #     st.write(
    #         "This platform enables pharmaceutical organizations to prioritize generic development "
    #         "programs using a unified, data-driven framework grounded in FDA Orange Book intelligence. "
    #         "By aligning BD, regulatory, R&D, and commercial teams around shared signals, it accelerates "
    #         "go/no-go decisions and improves execution confidence across the pipeline."
    #     )
    st.divider()
    st.markdown("### 🚀 Next-Level Execution Plan")

    # Style selector (VC / PE / BD)
    style = st.selectbox(
        "Output style",
        ["VC Pitch", "PE Diligence", "Corporate BD / IC Memo"],
        key="next_plan_style",
    )

    # Only generate after Analyze (same rule as your board summary)
    can_generate = bool(st.session_state.get("run_id"))

    # Reset cache if new Analyze OR style changed
    current_signature = f"{st.session_state.get('run_id')}::{style}"
    if st.session_state.get("next_plan_run_id") != current_signature:
        st.session_state.next_plan_text = None
        st.session_state.next_plan_run_id = current_signature

    if not can_generate:
        st.info("Run **Analyze** from the sidebar to generate the execution plan.")
    else:
        if st.session_state.next_plan_text is None:
            with st.spinner("Generating next-level execution plan…"):
                try:
                    # If you implemented compute_formulation_risk()
                    formulation_risk_level = formulation_risk.get("level") if isinstance(formulation_risk, dict) else formulation.get("risk_level", "Unknown")
                    formulation_risk_score = formulation_risk.get("score") if isinstance(formulation_risk, dict) else None

                    st.session_state.next_plan_text = build_next_level_plan_text(
                        llm=llm,
                        style=style,
                        drug=selected_drug,
                        formulation_type=formulation.get("formulation_type", "Unknown"),
                        formulation_risk_level=formulation_risk_level or "Unknown",
                        formulation_risk_score=formulation_risk_score,
                        competition_level=comp_level or "Unknown",
                        competition_count=comp_count,
                        ege_years=ege_years,
                        cmc_cost=cost,
                    )
                except Exception as e:
                    # Safe fallback (static) if LLM fails
                    st.session_state.next_plan_text = (
                        "**Next-Level Execution Plan (Commercial-Scale Readiness)**\n\n"
                        "1) **Formulation stability & scale-up validation:** Run focused stability and scale-up studies to confirm performance at commercial batch size.\n"
                        "2) **Supply-chain lock-in & cost certainty:** Secure supply agreements and price frameworks for critical raw materials to protect margins.\n"
                        "3) **Market access & pricing optimization:** Map reimbursement pathways and define pricing tiers to support adoption.\n"
                        "4) **Regulatory & exclusivity leverage:** Evaluate feasibility of a limited-duration exclusivity strategy (e.g., 180-day exclusivity) without assuming eligibility.\n"
                        "5) **Rapid-launch operational plan:** Prepare manufacturing, quality release, distribution, and launch readiness to capture the current low-competition window.\n\n"
                        f"_Note: Auto-generation failed ({e}). Showing fallback text._"
                    )

        st.markdown(st.session_state.next_plan_text)

# =================================================
# EGE TAB
# =================================================
with ege_tab:
    st.subheader("⏳ Earliest Generic Entry (EGE) Dashboard")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Products", len(products))
    col2.metric("Generic-Ready Now", len(generic_df))
    col3.metric("Expiring ≤ 12 Months", len(expiring_df))
    col4.metric("Tracked Opportunities", max(len(products) - len(generic_df), 0))

    st.divider()

    st.markdown("### 🔍 Selected Drug – EGE Detail")

    if not ob_data:
        st.info("Select a drug or patent to view Earliest Generic Entry.")
    else:
        ege_info = earliest_generic_entry(ob_data) or {}
        ege_date = ege_info.get("earliest_date")

        if ege_date:
            st.metric("Earliest Generic Entry", ege_date.strftime("%B %d, %Y"))
        else:
            st.success("No Orange Book blockers — generic eligible now")

        with st.expander("📄 Blocking Patents & Exclusivities"):
            patents_df = ob_data.get("patents")
            exclus_df = ob_data.get("exclusivities")

            if patents_df is not None and not patents_df.empty:
                st.markdown("**Patents**")
                st.dataframe(patents_df, use_container_width=True)
            else:
                st.caption("No listed blocking patents.")

            if exclus_df is not None and not exclus_df.empty:
                st.markdown("**Exclusivities**")
                st.dataframe(exclus_df, use_container_width=True)
            else:
                st.caption("No listed exclusivities.")

    st.divider()

    st.markdown("### 📅 Portfolio EGE Scanner")

    left, right = st.columns([1, 3])

    max_drugs = left.number_input(
        "Max drugs to scan",
        min_value=100,
        max_value=5000,
        value=800,
        step=100,
    )

    if left.button("⚡ Build / Refresh EGE Table", use_container_width=True):
        with st.spinner("Computing Earliest Generic Entry dates…"):
            st.session_state.ege_master_df = build_ege_table_cached(int(max_drugs))

    ege_master_df = st.session_state.get("ege_master_df")

    if ege_master_df is None or ege_master_df.empty:
        st.info("Click **Build / Refresh EGE Table** to generate portfolio EGE data.")
    else:
        f1, f2 = st.columns(2)
        max_years = f1.slider("Max Years to Entry", 0, 6, 3)
        status_filter = f2.multiselect("Status", ["Open", "Blocked"], ["Open", "Blocked"])

        filtered_df = (
            ege_master_df[
                (ege_master_df["Years to Entry"] <= max_years)
                & (ege_master_df["Status"].isin(status_filter))
            ]
            .sort_values("Years to Entry")
            .reset_index(drop=True)
        )

        st.dataframe(filtered_df, use_container_width=True, height=520)
# =====================================================
# STRATEGY TAB
# =====================================================
with strategy_tab:
    st.subheader("📊 Market Strategy")

    # -------------------------------------------------
    # Generic-ready drugs
    # -------------------------------------------------
    st.markdown("### 🟢 All Generic-Ready Drugs (No Listed Blockers)")
    st.metric("Generic-ready products", len(generic_df))

    if generic_df.empty:
        st.info("No generic-ready drugs found.")
    else:
        st.dataframe(generic_df, use_container_width=True, height=420)

    st.divider()

    # -------------------------------------------------
    # Expiring patents
    # -------------------------------------------------
    st.markdown("### ⏱ Patents Expiring Soon")

    months_new = st.slider(
        "Months ahead",
        min_value=1,
        max_value=48,
        value=st.session_state.months_horizon,
        step=1,
    )

    if months_new != st.session_state.months_horizon:
        st.session_state.months_horizon = months_new

    expiring_df2 = pd.DataFrame(
        find_expiring_patents(patents, st.session_state.months_horizon)
    )

    st.metric("Expiring patents", len(expiring_df2))

    if expiring_df2.empty:
        st.info("No patents expiring in the selected window.")
    else:
        st.dataframe(expiring_df2, use_container_width=True, height=420)

    st.divider()

    # -------------------------------------------------
    # Top-20 opportunity ranking (EXPLICIT trigger only)
    # -------------------------------------------------
    st.subheader("🏆 Top-20 Orange Book Opportunities (Auto-ranked)")

    # ---------------------------------
    # Session state (initialize once)
    # ---------------------------------
    st.session_state.setdefault("top20_opportunities", None)
    st.session_state.setdefault("top20_computed", False)

    # ---------------------------------
    # Explicit trigger only (NO auto-run)
    # ---------------------------------
    run_rank = st.button(
        "⚡ Run / Refresh Top-20 Ranking",
        use_container_width=True,
    )

    if run_rank:
        with st.spinner("Ranking opportunities from Orange Book signals…"):
            st.session_state.top20_opportunities = rank_top_orange_book_opportunities(
                products=products,
                patents=patents,
                exclus=exclus,
                top_n=20,
                max_drugs=1500,  # safety bound
            )
            st.session_state.top20_computed = True

    top20 = st.session_state.top20_opportunities

    # ---------------------------------
    # Display
    # ---------------------------------
    if top20 is None:
        st.info("Click **Run / Refresh Top-20 Ranking** to generate opportunities.")
    elif top20.empty:
        st.warning("No opportunities could be ranked from the current Orange Book data.")
    else:
        st.dataframe(top20, use_container_width=True, height=520)
# =====================================================
# AI TAB
# =====================================================
with ai_tab:
    st.subheader("🧠 AI Market Intelligence")

    # -----------------------------
    # Preconditions (NO st.stop in tabs)
    # -----------------------------
    if st.session_state.get("run_id") is None:
        st.info("Run **Analyze** from the sidebar to generate AI insights.")

    elif not selected_drug or formulation is None:
        st.warning("Missing analysis context. Please re-run Analyze.")

    else:
        # -----------------------------
        # Build prompt only once per run
        # -----------------------------
        if st.session_state.get("ai_summary") is None:
            ege_text = (
                "Open to generic entry now"
                if ege_years is None
                else f"{ege_years:.1f} years until earliest generic entry"
            )

            prompt = f"""
You are a US pharmaceutical strategy analyst advising senior leadership.

Drug: {selected_drug}
Formulation risk: {formulation.get('risk_level', 'Unknown')}
Competition level: {comp_level}
Earliest Generic Entry: {ege_text}

Write a concise executive analysis with the following structure:

1) Opportunity assessment (commercial attractiveness)
2) Key risks (IP, formulation, competition)
3) Recommended next steps (data, actions, or diligence)

Rules:
- Maximum 3 short paragraphs
- No legal advice
- No invented numbers or dates
- Professional, board-ready tone
"""

            with st.spinner("Generating AI market intelligence…"):
                try:
                    st.session_state.ai_summary = llm.invoke(prompt).content.strip()
                except Exception as e:
                    st.error(f"AI analysis failed: {e}")
                    st.session_state.ai_summary = None

        # -----------------------------
        # Display (SAFE)
        # -----------------------------
        if st.session_state.ai_summary:
            st.write(st.session_state.ai_summary)
import os

ORANGE_BOOK_DIR = "data/orange_book"

with data_upload:
    st.subheader("📂 Load Excel / CSV Orange Book Data")

    uploaded_file = st.file_uploader(
        "Upload Excel or CSV",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=False,
    )

    if uploaded_file:
        sheets = read_file_dynamic(uploaded_file)

        if not sheets:
            st.error("No readable sheets found.")
        else:
            sheet_names = list(sheets.keys())
            selected_sheet = st.selectbox("Select sheet", sheet_names)

            sheet_info = sheets[selected_sheet]

            if "error" in sheet_info:
                st.error(sheet_info["error"])
            else:
                st.dataframe(sheet_info["data"], use_container_width=True)

                st.divider()
                st.markdown("### 🚀 Promote as Orange Book Dataset")

                dataset_type = st.selectbox(
                    "Dataset type",
                    ["products", "patents", "exclusivities"],
                )

                if st.button("✅ Overwrite & Reload App", type="primary"):
                    os.makedirs(ORANGE_BOOK_DIR, exist_ok=True)

                    target_path = os.path.join(
                        ORANGE_BOOK_DIR,
                        f"{dataset_type}.csv",
                    )

                    # Save FULL dataset (not preview)
                    full_df = sheet_info["data"]
                    full_df.to_csv(target_path, index=False)

                    st.success(f"✅ `{dataset_type}.csv` updated")

                    reload_app_after_upload()

