# enrich_pubmed.py
import time
import requests
import pandas as pd

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

def pubmed_counts(query: str) -> tuple[int, list[str]]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": 20,  # store top PMIDs for traceability
    }
    r = requests.get(EUTILS, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    count = int(data["esearchresult"]["count"])
    pmids = data["esearchresult"].get("idlist", [])
    return count, pmids

def main(in_csv, out_csv, sleep_s=0.34):
    df = pd.read_csv(in_csv)

    pub_counts = []
    top_pmids = []

    for _, row in df.iterrows():
        sci = str(row["Scientific_Name"])
        # Simple query (you can expand with common names)
        q = f"\"{sci}\"[Title/Abstract] OR \"{sci}\"[All Fields]"
        try:
            c, pmids = pubmed_counts(q)
        except Exception:
            c, pmids = 0, []
        pub_counts.append(c)
        top_pmids.append("|".join(pmids))
        time.sleep(sleep_s)  # be polite to NCBI

    df["PubMed_Count"] = pub_counts
    df["Top_PubMed_PMIDs"] = top_pmids

    # Simple evidence score proxy
    df["Evidence_Score_0_100"] = df["PubMed_Count"].clip(upper=500).apply(lambda x: int((x/500)*100))

    df.to_csv(out_csv, index=False)
    print(f"✅ Enriched -> {out_csv}")

if __name__ == "__main__":
    main(
        in_csv="global_medicinal_plants_base_20000.csv",
        out_csv="global_medicinal_plants_enriched_pubmed_20000.csv",
    )
