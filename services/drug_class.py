def infer_drug_class(drug_name: str, route: str | None) -> str:
    name = (drug_name or "").lower()
    route = (route or "").lower()

    if route == "oral":
        if any(k in name for k in ["statin", "azole", "pril", "sartan"]):
            return "Small-molecule oral therapy (chronic use)"
        return "Oral small-molecule drug"

    if route == "topical":
        return "Topical dermatology formulation"

    if route == "injectable":
        if any(k in name for k in ["mab", "antibody"]):
            return "Biologic injectable (high-complexity)"
        return "Sterile injectable formulation"

    if route == "inhaled":
        return "Inhalation drug–device combination product"

    return "Small-molecule pharmaceutical product"
