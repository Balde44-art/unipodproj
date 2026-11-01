"""Variables liées à l'eau : distance au cours d'eau le plus proche et hauteur au-dessus du Niger.

Entrées (à produire avant) :
    data/processed/dem_bamako_utm.tif      (python -m src.features.terrain)
    data/raw/osm_water_bamako.geojson      (python -m src.data.download_water)

Lancement depuis la racine du projet :
    python -m src.features.water_distance

Résultats :
    data/processed/dist_water_bamako_utm.tif      distance (m) au cours d'eau le plus proche (tous types)
    data/processed/height_above_niger_utm.tif     altitude (m) au-dessus du Niger le plus proche
    outputs/figures/water_distance_bamako.png

Pourquoi le Niger seulement pour la hauteur ?
Une première version utilisait le pixel d'eau le plus proche, tous cours d'eau confondus. Elle
produisait des blocs aux bords nets (artefacts) car un petit ruisseau ou un étang situé plus haut
que le terrain voisin donnait des valeurs fausses. En se limitant au fleuve, la référence est une
ligne continue dont l'altitude varie lentement.

Limites à rappeler dans le mémoire :
- La hauteur est calculée en ligne droite vers le fleuve, pas le long du chemin d'écoulement
  (ce n'est pas le vrai HAND). Elle ne représente que le risque lié au fleuve.
- Le Copernicus DEM est un modèle de SURFACE (bâtiments, arbres inclus), pas de sol nu.
- L'altitude de référence du fleuve est le minimum local sur ~150 m, pour atténuer le bruit.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
DEM_UTM = ROOT / "data" / "processed" / "dem_bamako_utm.tif"
WATER = ROOT / "data" / "raw" / "osm_water_bamako.geojson"
DIST_OUT = ROOT / "data" / "processed" / "dist_water_bamako_utm.tif"
HEIGHT_OUT = ROOT / "data" / "processed" / "height_above_niger_utm.tif"
FIGURE = ROOT / "outputs" / "figures" / "water_distance_bamako.png"

NIGER_NAME = "niger"  # recherche insensible à la casse dans le champ « name » d'OSM


def distance_and_height(water_mask, dem, res, reference=None):
    """Distance (m) et différence d'altitude (m) avec le pixel d'eau le plus proche.

    water_mask : booléen, True là où il y a de l'eau.
    dem        : altitudes en mètres (NaN = pas de donnée).
    res        : taille d'un pixel en mètres.
    reference  : altitude de l'eau en chaque pixel (par défaut : le DEM lui-même).
    """
    # distance_transform_edt mesure la distance jusqu'au pixel « 0 » le plus proche :
    # on met donc 0 sur l'eau et 1 ailleurs.
    dist, (iy, ix) = ndimage.distance_transform_edt(
        ~water_mask, sampling=res, return_indices=True
    )
    if reference is None:
        reference = dem
    height = (dem - reference[iy, ix]).astype("float32")
    dist = dist.astype("float32")
    dist[np.isnan(dem)] = np.nan
    return dist, height


def river_reference(dem, mask, size=5):
    """Altitude de référence du cours d'eau : minimum local de l'altitude des pixels d'eau.

    Le minimum sur une fenêtre de `size` pixels (5 pixels = 150 m) atténue le bruit du DEM
    (ponts, végétation, rives) et approche mieux le niveau de l'eau.
    """
    ok = mask & ~np.isnan(dem)
    ref = np.where(ok, dem, np.inf)
    ref = ndimage.minimum_filter(ref, size=size)
    ref[np.isinf(ref)] = np.nan
    return ref.astype("float32")


def _rasterize(gdf, shape, transform):
    return rasterize(
        ((geom, 1) for geom in gdf.geometry),
        out_shape=shape,
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    ).astype(bool)


def run():
    with rasterio.open(DEM_UTM) as src:
        dem = src.read(1)
        profile = src.profile.copy()
        transform, crs, shape = src.transform, src.crs, (src.height, src.width)
        res = abs(transform.a)

    water = gpd.read_file(WATER).to_crs(crs)
    niger = water[water["name"].fillna("").str.contains(NIGER_NAME, case=False)]
    if niger.empty:
        raise RuntimeError(
            "Aucun objet nommé « Niger » dans le fichier OSM. Types présents : "
            + ", ".join(sorted(water["kind"].unique()))
        )

    mask_all = _rasterize(water, shape, transform)
    # Le Niger ne sert de référence que là où le DEM existe : sinon les pixels dont le fleuve le
    # plus proche est hors couverture du DEM restent vides (encoche visible sur la carte).
    mask_niger = _rasterize(niger, shape, transform) & ~np.isnan(dem)
    print(f"Pixels d'eau (tous cours d'eau) : {mask_all.sum()} | pixels Niger : {mask_niger.sum()} "
          f"(sur {mask_all.size})")
    if mask_niger.sum() == 0:
        raise RuntimeError("Le Niger est vide une fois rastérisé : vérifier la zone d'étude.")

    dist_all, _ = distance_and_height(mask_all, dem, res)
    ref = river_reference(dem, mask_niger)
    dist_niger, height = distance_and_height(mask_niger, dem, res, reference=ref)

    for path, arr in ((DIST_OUT, dist_all), (HEIGHT_OUT, height)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(arr, 1)

    print(f"Distance au cours d'eau le plus proche : médiane {np.nanmedian(dist_all):.0f} m | "
          f"{100 * np.nanmean(dist_all < 500):.0f} % des pixels à moins de 500 m")
    print(f"Distance au Niger : médiane {np.nanmedian(dist_niger):.0f} m | max {np.nanmax(dist_niger):.0f} m")
    print(f"Hauteur au-dessus du Niger : médiane {np.nanmedian(height):.0f} m | "
          f"{100 * np.nanmean(height < 5):.1f} % des pixels à moins de 5 m | "
          f"{100 * np.nanmean(height < 0):.1f} % sous le niveau de référence")

    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    im0 = axes[0].imshow(dist_all, cmap="viridis_r", vmax=5000)
    axes[0].set_title("Distance au cours d'eau le plus proche (m)")
    fig.colorbar(im0, ax=axes[0], shrink=0.8)
    im1 = axes[1].imshow(height, cmap="RdYlBu", vmin=0, vmax=80)
    axes[1].set_title("Hauteur au-dessus du Niger (m)")
    fig.colorbar(im1, ax=axes[1], shrink=0.8)
    axes[0].imshow(np.where(mask_all, 1.0, np.nan), cmap="gray_r", alpha=0.9)
    axes[1].imshow(np.where(mask_niger, 1.0, np.nan), cmap="gray_r", alpha=0.9)
    for ax in axes:
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    print(f"Figure enregistrée : {FIGURE}")


if __name__ == "__main__":
    run()
