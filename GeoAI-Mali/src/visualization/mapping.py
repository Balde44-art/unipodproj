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
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parents[2]
SCORE_TIF = ROOT / "data" / "processed" / "susceptibility_bamako_utm.tif"
ROBUST_TIF = ROOT / "data" / "processed" / "susceptibility_robust_utm.tif"
WATER_GEOJSON = ROOT / "data" / "raw" / "osm_water_bamako.geojson"
OUT_MAP = ROOT / "outputs" / "maps" / "susceptibility_bamako.html"

# Centre approximatif de Bamako (latitude, longitude)
BAMAKO_CENTER = (12.6392, -8.0029)

DISCLAIMER = """
<div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999; background: white;
            padding: 8px 12px; border: 1px solid #999; border-radius: 4px; max-width: 320px;
            font-size: 12px; font-family: sans-serif;">
<b>GeoAI Mali v0.1</b><br>
Indice relatif de susceptibilité (0 = faible, 1 = élevé) combinant la hauteur au-dessus du Niger,
la distance aux cours d'eau et la pente.<br>
<b>Ce n'est pas une prédiction d'inondation</b> : poids choisis par expert, aucune validation
sur des inondations observées.<br>
Données : Copernicus DEM, © OpenStreetMap contributors.
</div>
"""


def base_map(zoom: int = 11) -> folium.Map:
    """Retourne une carte Folium vide centrée sur Bamako."""
    return folium.Map(location=BAMAKO_CENTER, zoom_start=zoom, tiles="OpenStreetMap")


def raster_to_overlay(tif_path, cmap="YlOrRd", vmin=0.0, vmax=1.0):
    """Reprojette un raster en EPSG:4326 et le convertit en image RGBA pour Folium.

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

    scaled = np.clip((arr - vmin) / (vmax - vmin), 0, 1)
    rgba = matplotlib.colormaps[cmap](scaled)
    rgba[np.isnan(arr), 3] = 0.0  # pixels sans donnée : transparents
    return rgba, [[south, west], [north, east]]


def build_susceptibility_map(out_path=OUT_MAP):
    """Construit la carte interactive : indice, robustesse, cours d'eau."""
    fmap = base_map(zoom=11)

    image, bounds = raster_to_overlay(SCORE_TIF, cmap="YlOrRd")
    folium.raster_layers.ImageOverlay(
        image=image, bounds=bounds, opacity=0.65, name="Indice de susceptibilité (0-1)"
    ).add_to(fmap)

    if ROBUST_TIF.exists():
        image, bounds = raster_to_overlay(ROBUST_TIF, cmap="Blues")
        folium.raster_layers.ImageOverlay(
            image=image, bounds=bounds, opacity=0.65, name="Robustesse aux poids (0-1)", show=False
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

    fmap.get_root().html.add_child(folium.Element(DISCLAIMER))
    folium.LayerControl(collapsed=False).add_to(fmap)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(out_path))
    return fmap


if __name__ == "__main__":
    build_susceptibility_map()
    print(f"Carte enregistrée : {OUT_MAP}")
