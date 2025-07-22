import requests

def get_inat_taxon_id(scientific_name):
    url = "https://api.inaturalist.org/v1/taxa"
    params = {
        "q": scientific_name,
        "per_page": 1,
        "locale": "en"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    results = response.json()
    if results["total_results"] > 0:
        taxon = results["results"][0]
        return taxon["id"], taxon["name"]
    else:
        return None, None

taxon_id, taxon_name = get_inat_taxon_id("Miconia calvescens")
print(f"Taxon ID: {taxon_id}, Name: {taxon_name}")
