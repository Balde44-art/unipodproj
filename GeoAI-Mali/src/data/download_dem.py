"""Téléchargement du Copernicus DEM GLO-30 (~30 m) pour la zone de Bamako.

Les tuiles sont lues directement depuis le bucket public AWS `copernicus-dem-30m`
(fichiers COG) : seule la fenêtre utile est transférée, pas les tuiles entières.

Lancement depuis la racine du projet :
    python -m src.data.download_dem

Résultat : data/raw/dem_bamako_cop30.tif (EPSG:4326, altitude en mètres)
Source : https://docs.digitalearthafrica.org/en/latest/data_specs/COP_DEM_specs.html
"""

import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "data" / "raw" / "dem_bamako_cop30.tif"

# Zone d'étude : (ouest, sud, est, nord) en degrés. Bamako ~ (-8.00, 12.64).
BBOX = (-8.15, 12.50, -7.85, 12.80)

TILE_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
)


def tile_urls(bbox):
    """Liste des URLs des tuiles de 1°x1° qui recouvrent la zone d'étude.

    Le nom d'une tuile désigne son coin sud-ouest (ex. N12_W009 = lat 12 à 13, lon -9 à -8).
    """
    west, south, east, north = bbox
    urls = []
    for lat in range(math.floor(south), math.floor(north) + 1):
        for lon in range(math.floor(west), math.floor(east) + 1):
            urls.append(
                TILE_URL.format(
                    ns="N" if lat >= 0 else "S",
                    lat=abs(lat),
                    ew="E" if lon >= 0 else "W",
                    lon=abs(lon),
                )
            )
    return urls


def download_dem(bbox=BBOX, out_path=OUT_PATH):
    urls = tile_urls(bbox)
    print(f"{len(urls)} tuile(s) à lire :")
    for u in urls:
        print("  ", u)

    env = rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    )
    with env:
        datasets = [rasterio.open(u) for u in urls]
        try:
            # nodata=NaN : les pixels ajoutés par le mosaïquage hors couverture restent
            # « vides » (NaN) au lieu d'être remplis par 0 m, ce qui fausserait la pente.
            mosaic, transform = merge(datasets, bounds=bbox, nodata=np.nan)
            profile = datasets[0].profile.copy()
        finally:
            for ds in datasets:
                ds.close()

    profile.update(
        driver="GTiff",
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=transform,
        nodata=np.nan,
        compress="deflate",
        tiled=True,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(mosaic)

    print(f"DEM enregistré : {out_path}")
    print(f"Taille : {mosaic.shape[2]} x {mosaic.shape[1]} pixels")


if __name__ == "__main__":
    download_dem()
