"""Étiquettes d'inondation : détection de l'eau « nouvelle » sur Sentinel-1 (saison des pluies 2024).

Méthode (détection de changement, classique et simple) pour chaque date de la saison des pluies :
1. Passage en dB et filtrage du speckle (filtre moyen 3x3 sur l'intensité linéaire).
2. Référence sèche = médiane (en dB) des trois images de mars-avril 2024, même orbite.
3. Un pixel est « nouvellement inondé » si TOUTES ces conditions sont vraies :
     - il est sombre à la date étudiée (VV < T_WATER) : surface lisse = eau libre probable ;
     - il a baissé d'au moins |T_CHANGE| dB par rapport à la référence sèche ;
     - il n'était PAS déjà sombre en saison sèche (exclut eau permanente, routes goudronnées,
       ombres radar, sable lisse : surfaces sombres toute l'année) ;
     - l'image est valide à cet endroit (masque Sentinel-1) ;
     - la zone détectée contient au moins MIN_PIXELS pixels connectés (retire le bruit isolé).
4. Les cartes sont ramenées sur la grille de 30 m du DEM (part de pixel inondée) ; on exclut les
   pentes > MAX_SLOPE_DEG (artefacts radar) et on compte sur combien de dates chaque pixel est
   inondé (0 à 5).

Seuils choisis a priori (valeurs usuelles de la littérature, À JUSTIFIER ou à tester) :
    T_WATER = -18 dB, T_CHANGE = -3 dB, MIN_PIXELS = 8, MAX_SLOPE_DEG = 8, part inondée >= 0,3.

Lancement depuis la racine du projet (après download_sentinel1_dea et terrain/urban_mask) :
    python -m src.features.flood_labels

Résultats :
    data/processed/flood_s1_count_utm.tif   nombre de dates inondées (0 à 5), grille DEM 30 m
    outputs/figures/flood_labels_bamako.png

LIMITES (à écrire telles quelles dans le mémoire) :
- Ce sont des ÉTIQUETTES DÉRIVÉES D'UN CAPTEUR, pas une vérité terrain : elles ne valent que si la
  détection est correcte, et n'ont pas été validées sur le terrain.
- Une image tous les 12 jours : on voit l'eau présente à ces dates, pas le pic d'inondation.
- Le radar voit mal l'eau entre les bâtiments (double rebond) : sous-détection en ville dense.
- Les champs inondés ou les zones à végétation changeante peuvent donner de faux positifs.
- Une absence de détection (étiquette 0) ne prouve PAS l'absence d'inondation.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from scipy import ndimage

from src.data.download_sentinel1_dea import DRY_DATES, OUT_DIR as S1_DIR, WET_DATES

ROOT = Path(__file__).resolve().parents[2]
DEM_UTM = ROOT / "data" / "processed" / "dem_bamako_utm.tif"
SLOPE_UTM = ROOT / "data" / "processed" / "slope_bamako_utm.tif"
URBAN_UTM = ROOT / "data" / "processed" / "urban_mask_utm.tif"
COUNT_OUT = ROOT / "data" / "processed" / "flood_s1_count_utm.tif"
PERMANENT_OUT = ROOT / "data" / "processed" / "permanent_dark_utm.tif"
FIGURE = ROOT / "outputs" / "figures" / "flood_labels_bamako.png"

T_WATER = -18.0
T_CHANGE = -3.0
MIN_PIXELS = 8
MAX_SLOPE_DEG = 8.0
MIN_FRACTION = 0.3


def to_db(linear):
    return 10.0 * np.log10(np.maximum(linear, 1e-6))


def speckle_filter(linear, valid, size=3):
    """Filtre moyen sur l'intensité linéaire (réduit le speckle), en ignorant les pixels invalides."""
    filled = np.where(valid, linear, 0.0)
    num = ndimage.uniform_filter(filled.astype("float64"), size=size)
    den = ndimage.uniform_filter(valid.astype("float64"), size=size)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den == 0] = np.nan
    return out


def remove_small_regions(mask, min_pixels=MIN_PIXELS):
    """Supprime les groupes de pixels connectés (8 voisins) de moins de `min_pixels` pixels."""
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, labels, index=np.arange(1, n + 1))
    keep = np.concatenate([[False], sizes >= min_pixels])
    return keep[labels]


def detect_flood(wet_db, ref_db, valid):
    """Pixels nouvellement inondés à une date (voir la description en tête de fichier)."""
    with np.errstate(invalid="ignore"):
        dark_now = wet_db < T_WATER
        dropped = (wet_db - ref_db) < T_CHANGE
        dark_before = ref_db < T_WATER
    flood = dark_now & dropped & ~dark_before & valid
    return remove_small_regions(flood)


def read_s1(tag):
    """Lit VV (linéaire) et le masque de validité d'une date ; renvoie (VV filtré en dB, valid, profil)."""
    with rasterio.open(S1_DIR / f"vv_{tag}.tif") as src:
        vv, profile = src.read(1).astype("float64"), src.profile.copy()
    with rasterio.open(S1_DIR / f"mask_{tag}.tif") as src:
        valid = (src.read(1) > 0) & np.isfinite(vv) & (vv > 0)  # masque : 0 = invalide
    return to_db(speckle_filter(vv, valid)), valid, profile


def run():
    # 1. Référence sèche
    dry_stack = []
    for day in DRY_DATES:
        db, valid, profile = read_s1(day.replace("-", ""))
        db[~valid] = np.nan
        dry_stack.append(db)
    ref_db = np.nanmedian(np.stack(dry_stack), axis=0)
    ref_db = np.where(np.isnan(ref_db), 0.0, ref_db)  # pas de donnée de référence : traité comme terre
    print(f"Référence sèche : VV médiane {np.median(ref_db):.1f} dB ; "
          f"{100 * np.mean(ref_db < T_WATER):.1f} % de pixels sombres toute l'année (eau permanente, ombres, goudron)")

    # 2. Grille de sortie (DEM, UTM 30 m)
    with rasterio.open(DEM_UTM) as dem_src:
        dem = dem_src.read(1)
        grid = dem_src.profile.copy()
        dst_transform, dst_crs, shape = dem_src.transform, dem_src.crs, dem_src.shape
    with rasterio.open(SLOPE_UTM) as src:
        slope = src.read(1)
    outside = np.isnan(dem) | (slope > MAX_SLOPE_DEG)

    # Eau / surfaces sombres toute l'année (sert à les exclure des contrôles : ce ne sont pas des « non inondés »)
    perm_fraction = np.zeros(shape, dtype="float32")
    reproject(
        source=(ref_db < T_WATER).astype("float32"), destination=perm_fraction,
        src_transform=profile["transform"], src_crs=profile["crs"],
        dst_transform=dst_transform, dst_crs=dst_crs, resampling=Resampling.average,
    )
    perm_profile = grid.copy()
    perm_profile.update(dtype="uint8", nodata=255)
    with rasterio.open(PERMANENT_OUT, "w", **perm_profile) as dst:
        dst.write((perm_fraction >= 0.3).astype("uint8"), 1)

    # 3. Détection à chaque date de la saison des pluies, puis passage sur la grille de 30 m
    lat_mid = 0.5 * (profile["transform"].f + profile["transform"].f + profile["transform"].e * profile["height"])
    pixel_km2 = (abs(profile["transform"].a) * 111.32 * np.cos(np.radians(lat_mid))) * (
        abs(profile["transform"].e) * 110.57
    )
    count = np.zeros(shape, dtype="int16")
    fractions = []
    print("\nDate        eau nouvelle (km²)   pixels de 30 m inondés (après exclusions)")
    for day in WET_DATES:
        wet_db, valid, _ = read_s1(day.replace("-", ""))
        flood = detect_flood(wet_db, ref_db, valid)

        fraction = np.zeros(shape, dtype="float32")
        reproject(
            source=flood.astype("float32"), destination=fraction,
            src_transform=profile["transform"], src_crs=profile["crs"],
            dst_transform=dst_transform, dst_crs=dst_crs, resampling=Resampling.average,
        )
        flooded30 = (fraction >= MIN_FRACTION) & ~outside
        count += flooded30
        fractions.append(flooded30)
        print(f"{day}   {flood.sum() * pixel_km2:8.1f}            {flooded30.sum():8d}")

    count = np.where(np.isnan(dem), -1, count).astype("int16")
    out_profile = grid.copy()
    out_profile.update(dtype="int16", nodata=-1)
    COUNT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(COUNT_OUT, "w", **out_profile) as dst:
        dst.write(count, 1)

    valid_cells = count >= 0
    area30 = abs(dst_transform.a) * abs(dst_transform.e) / 1e6
    print(f"\nInondé au moins 1 date : {(count >= 1).sum() * area30:.1f} km² "
          f"({100 * (count >= 1).sum() / valid_cells.sum():.1f} % de la zone)")
    print(f"Inondé au moins 2 dates : {(count >= 2).sum() * area30:.1f} km² "
          f"({100 * (count >= 2).sum() / valid_cells.sum():.1f} % de la zone)")
    if URBAN_UTM.exists():
        with rasterio.open(URBAN_UTM) as src:
            urban = src.read(1) > 0
        print(f"Part des pixels « inondé au moins 1 date » situés en zone bâtie : "
              f"{100 * np.mean(urban[count >= 1]):.0f} % (la zone bâtie couvre {100 * urban[valid_cells].mean():.0f} % de la zone)")

    # 4. Figure
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    axes[0].imshow(ref_db, cmap="gray", vmin=-20, vmax=0)
    axes[0].set_title("Référence sèche : VV médiane (dB)")
    axes[1].imshow(np.where(valid_cells, fractions[2].astype(float), np.nan), cmap="Blues", vmin=0, vmax=1)
    axes[1].set_title(f"Eau nouvelle le {WET_DATES[2]} (grille 30 m)")
    im = axes[2].imshow(np.where(valid_cells, count, np.nan), cmap="YlGnBu", vmin=0, vmax=len(WET_DATES))
    axes[2].set_title(f"Nombre de dates inondées (sur {len(WET_DATES)})")
    fig.colorbar(im, ax=axes[2], shrink=0.8)
    for ax in axes:
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    print(f"Figure enregistrée : {FIGURE}")


if __name__ == "__main__":
    run()
