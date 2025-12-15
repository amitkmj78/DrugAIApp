def us_patent_outlook(drug_name):
    """
    v1 heuristic:
    - Explains Orange Book logic
    - No scraping yet (keeps it safe + simple)
    """
    return (
        f"For US small-molecule drugs like {drug_name}, the FDA Orange Book is the "
        "primary source of listed patents and regulatory exclusivities.\n\n"
        "Key points:\n"
        "• Listed patents may cover composition, formulation, or method of use\n"
        "• Patent expiration dates may be extended by pediatric exclusivity (+6 months)\n"
        "• Regulatory exclusivities (NCE, 3-year) are separate from patents\n\n"
        "For accurate expiry dates, Orange Book lookup by NDA and strength is required "
        "in v2 of this app."
    )
