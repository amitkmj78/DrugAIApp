def compute_herbal_opportunity(drug_name: str):
    """
    Advanced herbal opportunity scoring engine.
    Adds predictive toxicology, PK complexity,
    network pharmacology, synergy potential,
    plant ID risk, and quality control scoring.
    """

    name = drug_name.lower()

    # ==========================
    # 1️⃣ Demand Score
    # ==========================
    high_demand = [
        "ashwagandha",
        "turmeric",
        "curcumin",
        "ginseng",
        "ginkgo",
        "milk thistle",
        "berberine",
        "lion",
    ]

    demand_score = 85 if any(x in name for x in high_demand) else 60

    # ==========================
    # 2️⃣ Extraction / Formulation Complexity
    # ==========================
    complex_extraction = [
        "curcumin",
        "ginseng",
        "ginkgo",
        "cannabinoid",
        "alkaloid",
    ]

    complexity_score = 75 if any(x in name for x in complex_extraction) else 40

    # ==========================
    # 3️⃣ Predictive Toxicology
    # ==========================
    hepatotoxic = ["kava", "green tea extract"]
    anticoagulant = ["ginkgo", "garlic"]
    stimulant = ["ephedra", "yohimbine"]

    tox_flags = []

    if any(x in name for x in hepatotoxic):
        tox_flags.append("Hepatotoxicity Risk")
    if any(x in name for x in anticoagulant):
        tox_flags.append("Bleeding Interaction Risk")
    if any(x in name for x in stimulant):
        tox_flags.append("Cardiovascular Stimulation Risk")

    tox_risk_level = "Moderate" if tox_flags else "Low"

    # ==========================
    # 4️⃣ Pharmacokinetics (PK)
    # ==========================
    low_bioavailability = ["curcumin", "resveratrol"]

    if any(x in name for x in low_bioavailability):
        pk_profile = "Low Bioavailability – Advanced Formulation Needed"
    else:
        pk_profile = "Standard Oral Absorption"

    # ==========================
    # 5️⃣ Network Pharmacology
    # ==========================
    multi_target = [
        "ashwagandha",
        "ginseng",
        "turmeric",
        "ginkgo",
        "rhodiola",
    ]

    network_complexity = (
        "High (Multi-target botanical)"
        if any(x in name for x in multi_target)
        else "Moderate"
    )

    # ==========================
    # 6️⃣ Synergy Potential
    # ==========================
    synergy_score = 80 if network_complexity == "High (Multi-target botanical)" else 55

    # ==========================
    # 7️⃣ Plant Identification Risk
    # ==========================
    adulteration_risk = [
        "ginseng",
        "turmeric",
        "saffron",
        "ashwagandha",
    ]

    plant_id_risk = (
        "High – Requires DNA / HPLC verification"
        if any(x in name for x in adulteration_risk)
        else "Moderate"
    )

    # ==========================
    # 8️⃣ Quality Control Risk
    # ==========================
    heavy_metal_sensitive = ["turmeric", "ashwagandha"]

    qc_risk = (
        "High – Heavy metal & pesticide monitoring required"
        if any(x in name for x in heavy_metal_sensitive)
        else "Standard GMP controls sufficient"
    )

    # ==========================
    # 9️⃣ Composite Opportunity Score
    # ==========================
    composite_score = int(
        (demand_score * 0.35)
        + (complexity_score * 0.15)
        + (synergy_score * 0.2)
        + (70 if tox_risk_level == "Low" else 50) * 0.15
        + (60 if "High" in qc_risk else 75) * 0.15
    )

    # ==========================
    # Final Output
    # ==========================
    return {
        "Demand Score": demand_score,
        "Formulation Complexity": complexity_score,
        "Regulatory Risk": "Low (Dietary Supplement – DSHEA)",
        "Market Type": "OTC / Nutraceutical",

        # 🔬 New Scientific Layers
        "Predictive Toxicology": {
            "Risk Level": tox_risk_level,
            "Flags": tox_flags if tox_flags else ["No major predictive flags"]
        },

        "Pharmacokinetics": pk_profile,

        "Network Pharmacology": network_complexity,

        "Synergy Potential Score": synergy_score,

        "Plant Identification Risk": plant_id_risk,

        "Quality Control Risk": qc_risk,

        "Composite Opportunity Score": composite_score
    }
