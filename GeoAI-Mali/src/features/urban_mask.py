"""Masque des zones bâties à partir d'ESA WorldCover (classe 50 = « Built-up »).

Entrées : data/raw/worldcover_bamako_2021.tif (python -m src.data.download_worldcover)
          data/processed/dem_bamako_utm.tif    (python -m src.features.terrain)

Lancement depuis la racine du projet :
    python -m src.features.urban_mask

Résultats (même grille que l'indice de susceptibilité, UTM 30 m) :
    data/processed/built_fraction_utm.tif   part de bâti (0 à 1) dans chaque pixel de 30 m
    data/processed/urban_mask_utm.tif       1 = zone bâtie ou voisine du bâti, 0 = autre
    outputs/figures/urban_mask_bamako.png

Choix à justifier dans le mémoire (non appris sur des données) :
- seuil : un pixel de 30 m est « urbain » s'il contient au moins 25 % de bâti ;
- élargissement de 3 pixels (~90 m) pour inclure cours, jardins et rues attenantes aux bâtiments,
  que WorldCover classe en arbres ou sol nu.

Limite : WorldCover est une classification automatique (précision globale ~77 % en Afrique) ;
l'habitat informel ou aux toits en terre est souvent mal détecté.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
WORLDCOVER = ROOT / "data" / "raw" / "worldcover_bamako_2021.tif"
DEM_UTM = ROOT / "data" / "processed" / "dem_bamako_utm.tif"
FRACTION_OUT = ROOT / "data" / "processed" / "built_fraction_utm.tif"
MASK_OUT = ROOT / "data" / "processed" / "urban_mask_utm.tif"
FIGURE = ROOT / "outputs" / "figures" / "urban_mask_bamako.png"

BUILT_UP_CLASS = 50
THRESHOLD = 0.25
DILATE_PX = 3


def build_urban_mask(built_fraction, threshold=THRESHOLD, dilate_px=DILATE_PX):
    """Booléen : fraction de bâti >= seuil, puis élargissement de `dilate_px` pixels."""
    core = np.nan_to_num(built_fraction, nan=0.0) >= threshold
    return ndimage.binary_dilation(core, iterations=dilate_px)


def run():
    with rasterio.open(DEM_UTM) as dem_src:
        dem = dem_src.read(1)
        profile = dem_src.profile.copy()
        dst_transform, dst_crs, shape = dem_src.transform, dem_src.crs, dem_src.shape

    with rasterio.open(WORLDCOVER) as src:
        built = (src.read(1) == BUILT_UP_CLASS).astype("float32")
        fraction = np.zeros(shape, dtype="float32")
        reproject(
            source=built,
            destination=fraction,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.average,  # moyenne de pixels de 10 m = part de bâti
        )

    outside = np.isnan(dem)
    fraction[outside] = np.nan
    mask = build_urban_mask(fraction) & ~outside

    frac_profile = profile.copy()
    frac_profile.update(dtype="float32", nodata=np.nan)
    mask_profile = profile.copy()
    mask_profile.update(dtype="uint8", nodata=None)
    FRACTION_OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(FRACTION_OUT, "w", **frac_profile) as dst:
        dst.write(fraction, 1)
    with rasterio.open(MASK_OUT, "w", **mask_profile) as dst:
        dst.write(mask.astype("uint8"), 1)

    valid = ~outside
    print(f"Bâti (classe 50) : {100 * np.nanmean(fraction[valid] > 0):.0f} % des pixels de 30 m "
          f"contiennent un peu de bâti")
    print(f"Masque urbain : {100 * mask[valid].mean():.0f} % de la zone d'étude "
          f"(seuil {THRESHOLD:.0%} de bâti, élargi de {DILATE_PX} pixels)")

    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    im0 = axes[0].imshow(fraction, cmap="Greys", vmin=0, vmax=1)
    axes[0].set_title("Part de bâti par pixel de 30 m (ESA WorldCover)")
    fig.colorbar(im0, ax=axes[0], shrink=0.8)
    axes[1].imshow(np.where(valid, mask, np.nan), cmap="Oranges", vmin=0, vmax=1.4)
    axes[1].set_title("Masque urbain (zones comparées à la validation)")
    for ax in axes:
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    print(f"Figure enregistrée : {FIGURE}")


if __name__ == "__main__":
    run()
