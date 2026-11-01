"""Récupération des images radar Sentinel-1 (déjà corrigées du relief) via Digital Earth Africa.

Pourquoi DE Africa plutôt que le téléchargement des scènes brutes ? Les scènes Sentinel-1 GRD
pèsent ~1 Go chacune et demandent un traitement lourd (calibration, correction du relief). Le
produit `s1_rtc` de Digital Earth Africa est déjà prêt à l'analyse (~20 m, correction
radiométrique du relief avec le Copernicus DEM) et on ne lit que la fenêtre de Bamako.

Source : Digital Earth Africa, produit « Sentinel-1 Radiometric Terrain Corrected SAR
Backscatter » (s1_rtc), traité à partir de données Copernicus Sentinel-1. Valeurs VV/VH en
intensité LINÉAIRE (pas en dB). https://docs.digitalearthafrica.org/en/latest/data_specs/Sentinel-1_specs.html

Lancement depuis la racine du projet :
    python -m src.data.download_sentinel1_dea

Résultats : data/raw/s1/{vv,vh,mask}_AAAAMMJJ.tif (EPSG:4326, emprise de la zone d'étude).

Dates choisies (orbite 16 ascendante, une image tous les 12 jours, résultat de search_sentinel1) :
- saison des pluies 2024 : 14 août, 26 août, 7 septembre, 19 septembre, 1er octobre
  (catastrophe nationale déclarée le 2 septembre 2024, aggravation en septembre) ;
- référence sèche 2024 : 11 mars, 23 mars, 4 avril (même orbite : géométrie identique).
Les images de 2019 ne sont pas retenues : la plus proche après le 16 mai 2019 est à +9 jours.
"""

from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.merge import merge

from src.data.download_dem import BBOX

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "s1"

STAC_SEARCH = "https://explorer.digitalearth.africa/stac/search"
COLLECTION = "s1_rtc"
S3_REGION = "af-south-1"

WET_DATES = ["2024-08-14", "2024-08-26", "2024-09-07", "2024-09-19", "2024-10-01"]
DRY_DATES = ["2024-03-11", "2024-03-23", "2024-04-04"]
BANDS = ["vv", "vh", "mask"]


def to_https(href):
    """Convertit une adresse s3://bucket/clé en adresse HTTPS lisible par GDAL."""
    if href.startswith("s3://"):
        bucket, _, key = href[5:].partition("/")
        return f"https://{bucket}.s3.{S3_REGION}.amazonaws.com/{key}"
    return href


def search_items(day, bbox=BBOX):
    """Éléments STAC du produit s1_rtc qui intersectent la zone d'étude ce jour-là (UTC)."""
    body = {
        "collections": [COLLECTION],
        "bbox": list(bbox),
        "datetime": f"{day}T00:00:00Z/{day}T23:59:59Z",
        "limit": 50,
    }
    resp = requests.post(STAC_SEARCH, json=body, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"Recherche STAC : code {resp.status_code}. Début de la réponse :\n{resp.text[:500]}")
    return resp.json().get("features", [])


def read_band(items, band, bbox=BBOX):
    """Assemble la bande demandée de tous les éléments, découpée sur la zone d'étude."""
    hrefs = []
    for item in items:
        asset = item.get("assets", {}).get(band)
        if asset is None:
            raise KeyError(f"Bande « {band} » absente. Bandes disponibles : {sorted(item.get('assets', {}))}")
        hrefs.append(to_https(asset["href"]))

    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif")
    with env:
        datasets = [rasterio.open(h) for h in hrefs]
        try:
            nodata = 0 if band == "mask" else np.nan
            mosaic, transform = merge(datasets, bounds=bbox, nodata=nodata)
            profile = datasets[0].profile.copy()
        finally:
            for ds in datasets:
                ds.close()
    profile.update(
        driver="GTiff", height=mosaic.shape[1], width=mosaic.shape[2], transform=transform,
        nodata=nodata, compress="deflate", tiled=True,
    )
    return mosaic, profile


def download_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for label, dates in (("RÉFÉRENCE SÈCHE", DRY_DATES), ("SAISON DES PLUIES", WET_DATES)):
        print(f"\n=== {label} ===")
        for day in dates:
            items = search_items(day)
            if not items:
                print(f"{day} : aucune image s1_rtc trouvée (produit non disponible ce jour-là ?)")
                continue
            tag = day.replace("-", "")
            for band in BANDS:
                mosaic, profile = read_band(items, band)
                with rasterio.open(OUT_DIR / f"{band}_{tag}.tif", "w", **profile) as dst:
                    dst.write(mosaic)
                if band == "vv":
                    vv = mosaic[0]
                    valid = np.isfinite(vv) & (vv > 0)
                    db = 10 * np.log10(vv[valid])
                    print(f"{day} : {len(items)} élément(s), {vv.shape[1]} x {vv.shape[0]} pixels, "
                          f"{100 * valid.mean():.0f} % valides, VV médiane {np.median(db):.1f} dB, "
                          f"{100 * (db < -18).mean():.1f} % des pixels sous -18 dB (eau libre probable)")
    print(f"\nFichiers enregistrés dans : {OUT_DIR}")


if __name__ == "__main__":
    download_all()
