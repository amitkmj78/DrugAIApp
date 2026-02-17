import uuid
import pandas as pd
import random
import string

N = 1000  # change to 600 / 3000 / 20000

def random_latin_suffix(k=7):
    letters = string.ascii_lowercase
    return ''.join(random.choices(letters, k=k))

def alpha_tag(k=4):
    # letters only (no numbers), used only if we get stuck
    letters = string.ascii_uppercase
    return ''.join(random.choices(letters, k=k))

genera = [
    "Acacia","Acorus","Achillea","Adhatoda","Aegle","Aloe",
    "Alpinia","Andrographis","Angelica","Artemisia","Asparagus",
    "Azadirachta","Bacopa","Berberis","Boswellia","Calendula",
    "Camellia","Cassia","Centella","Cinnamomum","Curcuma",
    "Echinacea","Ephedra","Ficus","Ginkgo","Glycyrrhiza",
    "Gymnema","Harpagophytum","Hypericum","Inula","Lavandula",
    "Mentha","Moringa","Ocimum","Panax","Passiflora",
    "Phyllanthus","Plantago","Polygonum","Rauwolfia",
    "Rhodiola","Salvia","Scutellaria","Silybum",
    "Taraxacum","Terminalia","Thymus","Tinospora","Trigonella",
    "Uncaria","Valeriana","Withania","Zingiber"
]

families = [
    "Fabaceae","Asteraceae","Lamiaceae","Zingiberaceae",
    "Rutaceae","Solanaceae","Apiaceae","Euphorbiaceae",
    "Rosaceae","Poaceae","Araliaceae"
]

systems = [
    "Ayurveda","TCM","Western Herbal",
    "African Traditional","Amazonian","Unani"
]

primary_uses = [
    "Inflammation","Diabetes","Stress","Immune",
    "Liver","Cardiovascular","Cognitive","Digestive",
    "Respiratory","Metabolic","Sleep","Skin"
]

tox_levels = ["Low","Moderate","High"]
evidence_levels = ["Traditional","Preclinical","Clinical"]

# ---- Bigger name vocabulary = scalable uniqueness
adjectives = [
    "Sacred","Wild","Golden","Bitter","Cooling","Calming","Bright",
    "Ancient","Mountain","Forest","Desert","River","Silver","Green",
    "Red","White","Black","Fragrant","Healing","Resilient","Gentle",
    "Vital","Purifying","Soothing","Restorative","Strong","Rare"
]

forms = [
    "Root","Leaf","Bark","Flower","Seed","Fruit","Resin","Rhizome",
    "Extract","Tonic","Essence","Elixir","Infusion","Powder"
]

regions = [
    "Himalayan","Andean","Amazon","Saharan","Mediterranean",
    "Bengal","Sichuan","Kerala","Yunnan","Nile","Atlas","Balkan"
]

def build_common_name(genus: str) -> str:
    # No index. Large combinatorial space.
    adj = random.choice(adjectives)
    reg = random.choice(regions)
    form = random.choice(forms)
    use = random.choice(primary_uses)

    # Example: "Sacred Himalayan Curcuma Root (Inflammation)"
    return f"{adj} {reg} {genus} {form} ({use})"

rows = []
unique_species = set()
unique_common = set()

max_attempts = N * 50
attempts = 0

while len(rows) < N:
    attempts += 1
    if attempts > max_attempts:
        # last-resort: add letters-only tag (still no index numbers)
        # ensures we finish even with extreme collisions
        genus = random.choice(genera)
        species = random_latin_suffix()
        scientific_name = f"{genus} {species}"

        common_name = build_common_name(genus) + f" [{alpha_tag()}]"
        if scientific_name in unique_species or common_name in unique_common:
            continue

        unique_species.add(scientific_name)
        unique_common.add(common_name)

    genus = random.choice(genera)
    species = random_latin_suffix()
    scientific_name = f"{genus} {species}"

    if scientific_name in unique_species:
        continue

    common_name = build_common_name(genus)

    if common_name in unique_common:
        continue

    unique_species.add(scientific_name)
    unique_common.add(common_name)

    rows.append({
        "plant_id": str(uuid.uuid4()),
        "Scientific_Name": scientific_name,
        "Common_Name": common_name,
        "Family": random.choice(families),
        "Traditional_System": random.choice(systems),
        "Primary_Use": random.choice(primary_uses),
        "Toxicity_Level": random.choice(tox_levels),
        "Evidence_Level": random.choice(evidence_levels),
    })

df = pd.DataFrame(rows)

output_file = "data/global_medicinal_plants_unique.csv"
df.to_csv(output_file, index=False)

print("✅ File generated successfully:", output_file)
print("Rows:", len(df))
print("Unique common names:", df["Common_Name"].nunique())
print("Unique scientific names:", df["Scientific_Name"].nunique())
