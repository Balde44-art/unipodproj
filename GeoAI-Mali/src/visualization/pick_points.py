"""Carte pour relever les coordonnées des lieux de référence (inondés ou non).

Lancement depuis la racine du projet :
    python -m src.visualization.pick_points
Puis ouvrir outputs/maps/pick_points.html dans le navigateur.

Utilisation :
- La loupe en haut à gauche cherche un nom de lieu (ex. « Niamakoro, Bamako »).
- Taper le nom d'un quartier dans la barre de recherche en haut à gauche (ex. « Niamakoro, Bamako »).
- Passer en « Imagerie satellite » avec le sélecteur de couches pour repérer un quartier.
- Cliquer au CENTRE du quartier (un quartier fait 1 à 2 km : le rayon du CSV couvre l'incertitude).
- CLIQUER sur la carte : une bulle affiche la latitude et la longitude du point cliqué.
- Recopier ces valeurs dans data/reference/flood_reference_points.csv
  (lat, lon, flooded = 1 pour un lieu inondé, 0 pour un lieu connu comme non inondé,
  une source et une date dans les colonnes prévues).
- Points déjà dans le CSV : rouge = inondé, vert = non inondé.
- Points BLEUS = propositions d'OpenStreetMap (python -m src.data.locate_places), à vérifier.
"""

from pathlib import Path

import folium
import pandas as pd
from folium.plugins import Geocoder
from folium.plugins import Geocoder

ROOT = Path(__file__).resolve().parents[2]
POINTS_CSV = ROOT / "data" / "reference" / "flood_reference_points.csv"
PROPOSED_CSV = ROOT / "outputs" / "proposed_coordinates.csv"
OUT_MAP = ROOT / "outputs" / "maps" / "pick_points.html"
BAMAKO_CENTER = (12.6392, -8.0029)


def build_pick_map(out_path=OUT_MAP):
    fmap = folium.Map(location=BAMAKO_CENTER, zoom_start=12, tiles="OpenStreetMap")
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics",
        name="Imagerie satellite (Esri)",
    ).add_to(fmap)

    if POINTS_CSV.exists():
        points = pd.read_csv(POINTS_CSV).dropna(subset=["lat", "lon"])
        if "flooded" not in points.columns:
            points["flooded"] = 1
        for _, p in points.iterrows():
            flooded = int(p["flooded"]) == 1
            folium.CircleMarker(
                location=(p["lat"], p["lon"]),
                radius=8,
                color="red" if flooded else "green",
                fill=True,
                tooltip=f"{p['name']} ({'inondé' if flooded else 'non inondé'})",
            ).add_to(fmap)

    if PROPOSED_CSV.exists():
        for _, p in pd.read_csv(PROPOSED_CSV).iterrows():
            folium.CircleMarker(
                location=(p["lat"], p["lon"]),
                radius=7,
                color="blue",
                fill=True,
                tooltip=f"Proposition OSM pour {p['name']} : {p['osm_name']} ({p['place']}) "
                        f"{p['lat']}, {p['lon']}",
            ).add_to(fmap)

    Geocoder(collapsed=False, position="topleft", add_marker=True).add_to(fmap)
    # Barre de recherche (Nominatim/OpenStreetMap) : taper par exemple « Niamakoro, Bamako »
    Geocoder(collapsed=False, add_marker=True, position="topleft").add_to(fmap)
    folium.LatLngPopup().add_to(fmap)  # clic = affichage de lat/lon
    folium.LayerControl(collapsed=False).add_to(fmap)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(out_path))
    return out_path


if __name__ == "__main__":
    print(f"Carte enregistrée : {build_pick_map()}")
