"""Recherche des images radar Sentinel-1 disponibles sur Bamako (étape de faisabilité).

Objectif : savoir s'il existe des images Sentinel-1 prises PENDANT ou juste après les inondations
ciblées, et des images de référence en saison sèche, avant d'investir dans le traitement.

Source : catalogue public du Copernicus Data Space Ecosystem (API OData). La RECHERCHE ne demande
aucun compte ; le TÉLÉCHARGEMENT des images demandera un compte gratuit sur
https://dataspace.copernicus.eu (étape suivante, pas ici).

Lancement depuis la racine du projet :
    python -m src.data.search_sentinel1

Résultats :
    affichage par période : nombre d'images, dates, orbite, couverture de la zone d'étude
    outputs/s1_availability.csv

Produit recherché : Sentinel-1, mode IW, niveau GRD (images détectées, utilisables pour
cartographier l'eau). « Couvre toute la zone » = l'emprise de l'image contient entièrement la
zone d'étude (sinon l'image n'en couvre qu'une partie).

Remarque : Sentinel-1B est en panne depuis fin 2021. En 2019, deux satellites (1A et 1B)
fonctionnaient ; ensuite il n'y en a qu'un, donc moins d'images. Le script affiche ce qui existe.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import box, shape

from src.data.download_dem import BBOX

ROOT = Path(__file__).resolve().parents[2]
OUT_CSV = ROOT / "outputs" / "s1_availability.csv"

CATALOGUE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

# Périodes à examiner. event_date : date d'un événement précis (affiche l'écart en jours).
TARGETS = [
    {"name": "2019_evenement_16_mai", "start": "2019-04-15", "end": "2019-06-15", "event_date": "2019-05-16"},
    {"name": "2019_reference_seche", "start": "2019-02-01", "end": "2019-04-30", "event_date": None},
    {"name": "2024_saison_des_pluies", "start": "2024-07-01", "end": "2024-10-31", "event_date": None},
    {"name": "2024_reference_seche", "start": "2024-02-01", "end": "2024-04-30", "event_date": None},
]


def build_filter(bbox, start, end):
    """Filtre OData : Sentinel-1 GRD en mode IW qui intersecte la zone d'étude, entre deux dates."""
    west, south, east, north = bbox
    polygon = (
        f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
    )
    return (
        "Collection/Name eq 'SENTINEL-1' "
        f"and OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') "
        f"and ContentDate/Start gt {start}T00:00:00.000Z "
        f"and ContentDate/Start lt {end}T23:59:59.000Z "
        "and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        "and att/OData.CSC.StringAttribute/Value eq 'IW_GRDH_1S')"
    )


def parse_products(products, bbox, event_date=None):
    """Transforme la réponse OData en liste de lignes (dates, orbite, couverture)."""
    study_area = box(*bbox)
    event = date.fromisoformat(event_date) if event_date else None
    rows = []
    for p in products:
        attrs = {a["Name"]: a.get("Value") for a in p.get("Attributes", [])}
        acquired = p["ContentDate"]["Start"][:19]
        try:
            covered = shape(p["GeoFootprint"]).intersection(study_area).area / study_area.area
        except Exception:  # noqa: BLE001 : emprise absente ou illisible
            covered = None
        row = {
            "date": acquired,
            "satellite": p["Name"][:3],  # S1A, S1B, S1C
            "orbite": attrs.get("orbitDirection"),
            "orbite_relative": attrs.get("relativeOrbitNumber"),
            "polarisation": attrs.get("polarisationChannels"),
            "couverture_zone": None if covered is None else round(covered, 3),
            "couvre_toute_la_zone": covered is not None and covered >= 0.99,
            "nom": p["Name"],
        }
        if event is not None:
            row["jours_apres_evenement"] = (date.fromisoformat(acquired[:10]) - event).days
        rows.append(row)
    return rows


def search(bbox, start, end, event_date=None):
    params = {
        "$filter": build_filter(bbox, start, end),
        "$expand": "Attributes",
        "$orderby": "ContentDate/Start asc",
        "$top": 200,
    }
    resp = requests.get(CATALOGUE, params=params, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Le catalogue a répondu {resp.status_code}. Début de la réponse :\n{resp.text[:500]}"
        )
    products = resp.json().get("value", [])
    if products and not all("GeoFootprint" in p for p in products):
        print("  (emprise absente de la réponse ; champs reçus : " + ", ".join(sorted(products[0])) + ")")
    return parse_products(products, bbox, event_date)


def run():
    all_rows = []
    for target in TARGETS:
        print(f"\n=== {target['name']} ({target['start']} à {target['end']}) ===")
        rows = search(BBOX, target["start"], target["end"], target["event_date"])
        for r in rows:
            r["periode"] = target["name"]
        all_rows.extend(rows)

        n_full = sum(1 for r in rows if r["couvre_toute_la_zone"])
        n_unknown = sum(1 for r in rows if r["couverture_zone"] is None)
        print(f"{len(rows)} image(s) trouvée(s) : {n_full} couvrent toute la zone d'étude, "
              f"{n_unknown} de couverture inconnue.")
        for r in rows:
            cover = "?" if r["couverture_zone"] is None else f"{100 * r['couverture_zone']:.0f} %"
            extra = f" | {r['jours_apres_evenement']:+d} jours" if "jours_apres_evenement" in r else ""
            print(f"  {r['date']}  {r['satellite']}  orbite {r['orbite']} n°{r['orbite_relative']}  "
                  f"couverture {cover}{extra}")

    if all_rows:
        out = pd.DataFrame(all_rows)
        OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(OUT_CSV, index=False)
        print(f"\nDétail enregistré : {OUT_CSV}")
    else:
        print("\nAucune image trouvée : vérifier la connexion ou les dates.")


if __name__ == "__main__":
    run()
