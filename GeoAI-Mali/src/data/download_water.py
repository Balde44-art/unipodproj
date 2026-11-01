"""Téléchargement des cours d'eau et plans d'eau autour de Bamako depuis OpenStreetMap.

Source : API Overpass (https://overpass-api.de), données © contributeurs OpenStreetMap,
licence ODbL. Citer : « © OpenStreetMap contributors ».

Lancement depuis la racine du projet :
    python -m src.data.download_water

Résultat : data/raw/osm_water_bamako.geojson (lignes, EPSG:4326)

Choix de modélisation : tous les objets sont convertis en LIGNES (cours d'eau et
contours des plans d'eau). Un pixel situé à l'intérieur du fleuve est donc à une
petite distance non nulle de la berge. Limite à rappeler dans le mémoire.
"""

import time
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import LineString

from src.data.download_dem import BBOX

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "data" / "raw" / "osm_water_bamako.geojson"

# Marge autour de la zone d'étude pour que la distance reste correcte près des bords.
BUFFER_DEG = 0.05

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "GeoAI-Mali/0.1 (projet universitaire)"}


def build_query(bbox, buffer_deg=BUFFER_DEG):
    west, south, east, north = bbox
    s, w = south - buffer_deg, west - buffer_deg
    n, e = north + buffer_deg, east + buffer_deg
    box = f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}"  # Overpass : sud, ouest, nord, est
    return f"""
[out:json][timeout:120];
(
  way["waterway"~"^(river|stream|canal|drain|riverbank)$"]({box});
  way["natural"="water"]({box});
  relation["natural"="water"]({box});
  relation["waterway"="riverbank"]({box});
);
out geom;
"""


def elements_to_rows(elements):
    """Convertit la réponse Overpass en liste de lignes (dict avec géométrie shapely)."""
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        kind = tags.get("waterway") or tags.get("natural") or "autre"
        geometries = []
        if el.get("type") == "way" and "geometry" in el:
            geometries.append(el["geometry"])
        elif el.get("type") == "relation":
            for member in el.get("members", []):
                if member.get("type") == "way" and "geometry" in member:
                    geometries.append(member["geometry"])
        for geom in geometries:
            coords = [(p["lon"], p["lat"]) for p in geom]
            if len(coords) >= 2:
                rows.append(
                    {
                        "osm_id": el["id"],
                        "osm_type": el["type"],
                        "kind": kind,
                        "name": tags.get("name"),
                        "geometry": LineString(coords),
                    }
                )
    return rows


def query_overpass(query):
    last_error = None
    for url in OVERPASS_URLS:
        try:
            print(f"Requête Overpass : {url}")
            resp = requests.post(url, data={"data": query}, headers=HEADERS, timeout=180)
            resp.raise_for_status()
            return resp.json()["elements"]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f"  échec ({exc}), essai suivant…")
            time.sleep(2)
    raise RuntimeError(f"Aucun serveur Overpass n'a répondu : {last_error}")


def download_water(bbox=BBOX, out_path=OUT_PATH):
    elements = query_overpass(build_query(bbox))
    rows = elements_to_rows(elements)
    if not rows:
        raise RuntimeError("Aucun élément d'eau trouvé : vérifier la zone d'étude.")

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_path, driver="GeoJSON")

    print(f"{len(elements)} objets OSM -> {len(gdf)} segments de lignes")
    print(gdf["kind"].value_counts().to_string())
    noms = sorted({n for n in gdf["name"].dropna()})
    if noms:
        print("Noms trouvés :", ", ".join(noms[:15]))
    print(f"Enregistré : {out_path}")


if __name__ == "__main__":
    download_water()
