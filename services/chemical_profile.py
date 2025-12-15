def extract_chemical_profile(products_df):
    """
    Returns a structured chemical composition summary
    based on Orange Book product records.
    """

    if products_df is None or products_df.empty:
        return None

    # Use first RLD / reference-like product if available
    row = products_df.iloc[0]
    
    ingredient = row.get("ActiveIngredient", "Unknown")
    strength = row.get("strength", "Unknown")
    dosage_form = row.get("Dosage_Form", "Unknown")
    route = row.get("df;route", "Unknown")

    # Simple salt / form inference
    salt_forms = [
        "hydrochloride", "sodium", "potassium", "mesylate",
        "phosphate", "acetate", "tartrate", "sulfate"
    ]

    salt = "Free base / not specified"
    ing_lower = ingredient.lower()
    for s in salt_forms:
        if s in ing_lower:
            salt = s.capitalize()
            break

    return {
        "API": ingredient,
        "Salt / Form": salt,
        "Strength": strength,
        "Dosage Form": dosage_form,
        "Route": route,
    }
