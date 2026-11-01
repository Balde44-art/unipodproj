"""Téléchargement d'ESA WorldCover 2021 (10 m, v200) pour la zone de Bamako.

Source : ESA WorldCover 2021 v200, licence CC BY 4.0.
Citer : « © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021)
processed by ESA WorldCover consortium ».
Les tuiles (COG de 3° x 3°, nommées par leur coin sud-ouest) sont lues directement sur le bucket
public AWS `esa-worldcover` : seule la fenêtre utile est transférée.

Lancement depuis la racine du projet :
    python -m src.data.download_worldcover

Résultat : data/raw/worldcover_bamako_2021.tif (EPSG:4326, classes entières)
Légende : 10 arbres, 20 arbustes, 30 prairie, 40 cultures, 50 BÂTI, 60 sol nu, 70 neige/glace,
80 eau, 90 zones humides, 95 mangrove, 100 mousses/lichens ; 0 = pas de donnée.

Si le téléchargement échoue (nom de fichier ou connexion), télécharger la tuile N12W009 sur
https://esa-worldcover.org/en/data-access et la copier sous le nom
data/raw/worldcover_tile_N12W009.tif : le script la découpera à la place.
"""

import math
from pathlib import Path

import rasterio
from rasterio.merge import merge

from src.data.download_dem import BBOX

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "data" / "raw" / "worldcover_bamako_2021.tif"
LOCAL_TILE = ROOT / "data" / "raw" / "worldcover_tile_N12W009.tif"

TILE_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{ns}{lat:02d}{ew}{lon:03d}_Map.tif"
)


def tile_urls(bbox):
    """URLs des tuiles de 3°x3° qui recouvrent la zone d'étude (coin sud-ouest = multiple de 3)."""
    west, south, east, north = bbox
    urls = []
    for lat0 in range(3 * math.floor(south / 3), 3 * math.floor(north / 3) + 1, 3):
        for lon0 in range(3 * math.floor(west / 3), 3 * math.floor(east / 3) + 1, 3):
            urls.append(
                TILE_URL.format(
                    ns="N" if lat0 >= 0 else "S",
                    lat=abs(lat0),
                    ew="E" if lon0 >= 0 else "W",
                    lon=abs(lon0),
                )
            )
    return urls


def download_worldcover(bbox=BBOX, out_path=OUT_PATH):
    if LOCAL_TILE.exists():
        sources = [str(LOCAL_TILE)]
        print(f"Tuile locale utilisée : {LOCAL_TILE}")
    else:
        sources = tile_urls(bbox)
        print(f"{len(sources)} tuile(s) à lire :")
        for u in sources:
            print("  ", u)

    env = rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    )
    with env:
        try:
            datasets = [rasterio.open(s) for s in sources]
        except rasterio.errors.RasterioIOError as exc:
            raise SystemExit(
                f"Impossible d'ouvrir la tuile : {exc}\n"
                "Télécharger la tuile N12W009 sur https://esa-worldcover.org/en/data-access "
                f"et l'enregistrer sous {LOCAL_TILE}, puis relancer."
            )
        try:
            mosaic, transform = merge(datasets, bounds=bbox, nodata=0)
            profile = datasets[0].profile.copy()
        finally:
            for ds in datasets:
                ds.close()

    profile.update(
        driver="GTiff",
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=transform,
        nodata=0,
        compress="deflate",
        tiled=True,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(mosaic)
    print(f"WorldCover enregistré : {out_path} ({mosaic.shape[2]} x {mosaic.shape[1]} pixels)")


if __name__ == "__main__":
    download_worldcover()
