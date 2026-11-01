"""Cartographie interactive avec Folium.

Lancement depuis la racine du projet (après susceptibility) :
    python -m src.visualization.mapping

Résultat : outputs/maps/susceptibility_bamako.html (à ouvrir dans le navigateur)
"""

from pathlib import Path

import folium
import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parents[2]
SCORE_TIF = ROOT / "data" / "processed" / "susceptibility_bamako_utm.tif"
ROBUST_TIF = ROOT / "data" / "processed" / "susceptibility_robust_utm.tif"
FLUVIAL_TIF = ROOT / "data" / "processed" / "susceptibility_fluvial_utm.tif"
LOCAL_TIF = ROOT / "data" / "processed" / "susceptibility_local_utm.tif"
FLOOD_COUNT_TIF = ROOT / "data" / "processed" / "flood_s1_count_utm.tif"
POINTS_CSV = ROOT / "data" / "reference" / "flood_reference_points.csv"
WATER_GEOJSON = ROOT / "data" / "raw" / "osm_water_bamako.geojson"
OUT_MAP = ROOT / "outputs" / "maps" / "susceptibility_bamako.html"

# Centre approximatif de Bamako (latitude, longitude)
BAMAKO_CENTER = (12.6392, -8.0029)

DISCLAIMER = """
<div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999; background: white;
            padding: 8px 12px; border: 1px solid #999; border-radius: 4px; max-width: 340px;
            font-size: 12px; font-family: sans-serif;">
<b>GeoAI Mali v0.3</b><br>
Indice relatif de susceptibilité (0 = faible, 1 = élevé) : hauteur au-dessus du Niger, distance
aux cours d'eau, pente et indice d'humidité topographique (TWI).<br>
<b>Ce n'est pas une prédiction d'inondation.</b> Poids choisis par expert.<br>
<b>Composante fluviale</b> (hauteur + distance) : cohérente avec l'eau détectée par radar
Sentinel-1 en 2024 (étiquettes dérivées d'un capteur, sans vérification terrain).<br>
<b>Composante locale</b> (pente + TWI) : <b>non validée</b>. Le radar ne voit pas l'inondation urbaine.<br>
Données : Copernicus DEM, ESA WorldCover, Sentinel-1 (Digital Earth Africa), © OpenStreetMap contributors.
</div>
"""


def base_map(zoom: int = 11) -> folium.Map:
    """Retourne une carte Folium vide centrée sur Bamako."""
    return folium.Map(location=BAMAKO_CENTER, zoom_start=zoom, tiles="OpenStreetMap")


def raster_to_overlay(tif_path, cmap="YlOrRd", vmin=0.0, vmax=1.0, mask_below=None):
    """Reprojette un raster en EPSG:4326 et le convertit en image RGBA pour Folium.

    mask_below : les valeurs strictement inférieures sont rendues transparentes (ex. 1 pour un comptage).
    Renvoie (image RGBA, [[sud, ouest], [nord, est]]).
    """
    dst_crs = "EPSG:4326"
    with rasterio.open(tif_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        arr = np.full((height, width), np.nan, dtype="float32")
        reproject(
            source=rasterio.band(src, 1),
            destination=arr,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    west, north = transform.c, transform.f
    east = west + transform.a * width
    south = north + transform.e * height

    if mask_below is not None:
        arr = np.where(arr < mask_below, np.nan, arr)
    scaled = np.clip((arr - vmin) / (vmax - vmin), 0, 1)
    rgba = matplotlib.colormaps[cmap](scaled)
    rgba[np.isnan(arr), 3] = 0.0  # pixels sans donnée : transparents
    return rgba, [[south, west], [north, east]]


def add_reference_points(fmap):
    """Quartiers de référence déjà localisés (rouge = cité comme inondé). Les lieux sans coordonnées sont ignorés."""
    if not POINTS_CSV.exists():
        return
    points = pd.read_csv(POINTS_CSV).dropna(subset=["lat", "lon"])
    if points.empty:
        return
    group = folium.FeatureGroup(name="Quartiers de référence (cités comme inondés)", show=True)
    for _, p in points.iterrows():
        flooded = int(p.get("flooded", 1)) == 1
        folium.CircleMarker(
            location=(p["lat"], p["lon"]), radius=7, color="red" if flooded else "green",
            fill=True, tooltip=f"{p['name']} ({'inondé' if flooded else 'non inondé'}, {p.get('date', '')})",
        ).add_to(group)
    group.add_to(fmap)


def build_susceptibility_map(out_path=OUT_MAP):
    """Construit la carte interactive : indice, composantes, robustesse, eau radar, cours d'eau, quartiers."""
    fmap = base_map(zoom=11)

    image, bounds = raster_to_overlay(SCORE_TIF, cmap="YlOrRd")
    folium.raster_layers.ImageOverlay(
        image=image, bounds=bounds, opacity=0.65, name="Indice de susceptibilité (0-1)"
    ).add_to(fmap)

    optional_layers = [
        (FLUVIAL_TIF, "YlOrRd", 0.0, 1.0, None, "Composante fluviale (hauteur + distance)"),
        (LOCAL_TIF, "YlOrRd", 0.0, 1.0, None, "Composante locale (pente + TWI), NON validée"),
        (ROBUST_TIF, "Blues", 0.0, 1.0, None, "Robustesse aux poids (0-1)"),
        (FLOOD_COUNT_TIF, "Blues", 0.0, 5.0, 1.0, "Eau détectée par radar Sentinel-1, 2024 (nb de dates sur 5)"),
    ]
    for tif, cmap, vmin, vmax, mask_below, label in optional_layers:
        if tif.exists():
            image, bounds = raster_to_overlay(tif, cmap=cmap, vmin=vmin, vmax=vmax, mask_below=mask_below)
            folium.raster_layers.ImageOverlay(
                image=image, bounds=bounds, opacity=0.65, name=label, show=False
            ).add_to(fmap)

    if WATER_GEOJSON.exists():
        water = gpd.read_file(WATER_GEOJSON)[["kind", "name", "geometry"]]
        folium.GeoJson(
            water,
            name="Cours d'eau (OpenStreetMap)",
            style_function=lambda f: {"color": "#1f78b4", "weight": 1.2},
            tooltip=folium.GeoJsonTooltip(fields=["name", "kind"], aliases=["Nom", "Type"]),
            show=True,
        ).add_to(fmap)

    add_reference_points(fmap)

    fmap.get_root().html.add_child(folium.Element(DISCLAIMER))
    folium.LayerControl(collapsed=False).add_to(fmap)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(out_path))
    return fmap


if __name__ == "__main__":
    build_susceptibility_map()
    print(f"Carte enregistrée : {OUT_MAP}")
