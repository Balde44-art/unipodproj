"""Variables de terrain à partir du DEM : altitude (en mètres) et pente (en degrés).

Étapes :
1. Reprojection du DEM de EPSG:4326 (degrés) vers EPSG:32629 (UTM zone 29N, mètres),
   car une pente ne se calcule correctement que dans une unité de distance horizontale
   identique à l'unité verticale.
2. Pente = angle de la surface, déduit du gradient d'altitude (np.gradient).

Lancement depuis la racine du projet (après download_dem) :
    python -m src.features.terrain

Résultats :
    data/processed/dem_bamako_utm.tif
    data/processed/slope_bamako_utm.tif
    outputs/figures/dem_slope_bamako.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parents[2]
RAW_DEM = ROOT / "data" / "raw" / "dem_bamako_cop30.tif"
DEM_UTM = ROOT / "data" / "processed" / "dem_bamako_utm.tif"
SLOPE_UTM = ROOT / "data" / "processed" / "slope_bamako_utm.tif"
FIGURE = ROOT / "outputs" / "figures" / "dem_slope_bamako.png"

DST_CRS = "EPSG:32629"  # UTM zone 29N (couvre -12° à -6° de longitude)
RESOLUTION = 30.0  # mètres


def reproject_dem(src_path=RAW_DEM, dst_path=DEM_UTM, dst_crs=DST_CRS, res=RESOLUTION):
    """Reprojette le DEM en mètres et renvoie (tableau d'altitude, profil raster)."""
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=res
        )
        profile = src.profile.copy()
        profile.update(
            crs=dst_crs,
            transform=transform,
            width=width,
            height=height,
            dtype="float32",
            nodata=np.nan,
            compress="deflate",
        )
        dem = np.full((height, width), np.nan, dtype="float32")
        reproject(
            source=rasterio.band(src, 1),
            destination=dem,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(dem, 1)
    return dem, profile


def slope_degrees(dem, res=RESOLUTION):
    """Pente en degrés (0 = plat, 90 = vertical) pour un DEM en mètres, pixels carrés de `res` mètres."""
    dz_dy, dz_dx = np.gradient(dem, res)
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype("float32")


def run():
    dem, profile = reproject_dem()
    slope = slope_degrees(dem)

    SLOPE_UTM.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(SLOPE_UTM, "w", **profile) as dst:
        dst.write(slope, 1)

    print(f"Altitude : min {np.nanmin(dem):.0f} m | moyenne {np.nanmean(dem):.0f} m | max {np.nanmax(dem):.0f} m")
    print(f"Pente    : moyenne {np.nanmean(slope):.2f}° | max {np.nanmax(slope):.1f}° | "
          f"{100 * np.nanmean(slope < 2):.0f} % des pixels sous 2°")

    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    im0 = axes[0].imshow(dem, cmap="terrain")
    axes[0].set_title("Altitude (m) — Copernicus DEM GLO-30")
    fig.colorbar(im0, ax=axes[0], shrink=0.8)
    im1 = axes[1].imshow(slope, cmap="magma_r", vmax=15)
    axes[1].set_title("Pente (°)")
    fig.colorbar(im1, ax=axes[1], shrink=0.8)
    for ax in axes:
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    print(f"Figure enregistrée : {FIGURE}")


if __name__ == "__main__":
    run()
