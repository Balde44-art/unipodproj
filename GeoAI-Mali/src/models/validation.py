"""Validation préliminaire de l'indice de susceptibilité sur des lieux inondés (ou non) connus.

IMPORTANT : ceci n'est PAS une évaluation statistique de modèle tant que les points de référence
sont peu nombreux. On regarde si les lieux documentés comme inondés obtiennent un indice élevé
par rapport au reste de la zone d'étude, et quels critères portent ce résultat.

Entrée : data/reference/flood_reference_points.csv
    colonnes : name, commune, flooded, lat, lon, radius_m, date, certainty, source, notes
    flooded = 1 (inondation connue) ou 0 (lieu connu comme non inondé) ; 1 par défaut si absent.
    Les lignes sans lat/lon sont ignorées : il faut d'abord les localiser.

Pour chaque lieu :
- indice moyen dans un disque de rayon `radius_m` autour du point ;
- percentile de ce score moyen parmi tous les disques possibles de la zone d'étude
  (100 = plus exposé que toutes les autres zones) ;
- percentile de chaque critère pris seul (pct_height, pct_distance, pct_slope, pct_twi) : montre
  quels critères portent le résultat et lesquels le tirent vers le bas ;
- robustesse moyenne si la carte de robustesse existe.

S'il y a au moins 2 lieux inondés ET 2 lieux non inondés, un AUC est calculé : probabilité qu'un
lieu inondé tire un score plus élevé qu'un lieu non inondé (0,5 = hasard, 1 = parfait).
Avec si peu de points, c'est une indication, pas une mesure fiable.

Mise en garde : ne pas régler les poids de l'indice pour « bien classer » ces quelques points :
ce serait de l'ajustement sur le jeu de validation. Les poids restent ceux choisis a priori.

Biais à rappeler : la zone d'étude contient des collines et des zones non habitées. Si le fichier
data/processed/urban_mask_utm.tif existe, la comparaison se fait uniquement avec les zones bâties.

Lancement depuis la racine du projet :
    python -m src.models.validation
"""

from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform as warp_transform
from scipy.signal import fftconvolve
from scipy.stats import rankdata

from src.features import susceptibility as susc

ROOT = Path(__file__).resolve().parents[2]
POINTS_CSV = ROOT / "data" / "reference" / "flood_reference_points.csv"
SCORE_TIF = ROOT / "data" / "processed" / "susceptibility_bamako_utm.tif"
ROBUST_TIF = ROOT / "data" / "processed" / "susceptibility_robust_utm.tif"
URBAN_MASK_TIF = ROOT / "data" / "processed" / "urban_mask_utm.tif"
OUT_CSV = ROOT / "outputs" / "validation_results.csv"


def disc_kernel(radius_px):
    r = int(np.ceil(radius_px))
    y, x = np.ogrid[-r : r + 1, -r : r + 1]
    return (x * x + y * y <= radius_px**2).astype("float32")


def local_mean(arr, radius_px, min_valid_fraction=0.5):
    """Moyenne de `arr` dans un disque centré sur chaque pixel (NaN ignorés).

    Le résultat est NaN si moins de `min_valid_fraction` du disque contient des données.
    """
    valid = ~np.isnan(arr)
    kernel = disc_kernel(radius_px)
    num = fftconvolve(np.where(valid, arr, 0.0).astype("float64"), kernel, mode="same")
    den = fftconvolve(valid.astype("float64"), kernel, mode="same")
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = num / den
    mean[den < min_valid_fraction * kernel.sum()] = np.nan
    return mean.astype("float32")


def percentile_of(value, candidates):
    """Percentile de `value` parmi les zones candidates (rang moyen en cas d'égalité)."""
    below = np.mean(candidates < value)
    equal = np.mean(candidates == value)
    return 100.0 * float(below + 0.5 * equal)


def auc(positives, negatives):
    """AUC (Mann-Whitney) : probabilité qu'un positif ait un score plus haut qu'un négatif."""
    pos, neg = np.asarray(positives, float), np.asarray(negatives, float)
    ranks = rankdata(np.concatenate([pos, neg]))
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def run():
    points = pd.read_csv(POINTS_CSV)
    if "flooded" not in points.columns:
        points["flooded"] = 1
    points["flooded"] = points["flooded"].fillna(1).astype(int)
    for name in points[points["lat"].isna() | points["lon"].isna()]["name"]:
        print(f"[à localiser] {name} : lat/lon manquants, ligne ignorée.")
    points = points.dropna(subset=["lat", "lon"]).copy()
    if points.empty:
        raise RuntimeError("Aucun point localisé dans le fichier de référence.")

    with rasterio.open(SCORE_TIF) as src:
        score = src.read(1)
        res = abs(src.transform.a)
        crs, transform = src.crs, src.transform
        height, width = src.shape
    robust = None
    if ROBUST_TIF.exists():
        with rasterio.open(ROBUST_TIF) as src:
            robust = src.read(1)
    urban = None
    if URBAN_MASK_TIF.exists():
        with rasterio.open(URBAN_MASK_TIF) as src:
            urban = src.read(1) > 0
        print("Comparaison restreinte aux zones bâties (urban_mask_utm.tif).")
    else:
        print("ATTENTION : pas de masque urbain. La comparaison inclut collines et zones "
              "non habitées : le percentile est favorable aux quartiers riverains.")

    # Critères normalisés (même méthode que l'indice) pour le détail par critère
    layers = {}
    for name, path in susc.PATHS.items():
        with rasterio.open(path) as src:
            layers[name] = susc.normalize(name, src.read(1))

    cache = {}  # rayon (pixels) -> cartes de moyennes locales

    def maps_for(radius_px):
        if radius_px not in cache:
            cache[radius_px] = {"score": local_mean(score, radius_px)}
            for k, layer in layers.items():
                cache[radius_px][k] = local_mean(layer, radius_px)
            if robust is not None:
                cache[radius_px]["robust"] = local_mean(robust, radius_px)
        return cache[radius_px]

    def candidates_of(mean_map):
        keep = ~np.isnan(mean_map)
        if urban is not None:
            keep &= urban
        return mean_map[keep]

    rows = []
    for _, p in points.iterrows():
        xs, ys = warp_transform("EPSG:4326", crs, [float(p["lon"])], [float(p["lat"])])
        row, col = rasterio.transform.rowcol(transform, xs[0], ys[0])
        if not (0 <= row < height and 0 <= col < width):
            print(f"[hors zone] {p['name']} est en dehors de la zone d'étude.")
            continue

        maps = maps_for(float(p["radius_m"]) / res)
        value = maps["score"][row, col]
        if np.isnan(value):
            print(f"[sans données] {p['name']} : trop peu de pixels valides dans le disque.")
            continue

        result = {
            "name": p["name"],
            "flooded": int(p["flooded"]),
            "score_moyen": round(float(value), 3),
            "pct_total": round(percentile_of(value, candidates_of(maps["score"])), 1),
        }
        for k in susc.CRITERIA:
            v = maps[k][row, col]
            result[f"pct_{k}"] = round(percentile_of(v, candidates_of(maps[k])), 1) if not np.isnan(v) else np.nan
        if robust is not None:
            result["robustesse"] = round(float(maps["robust"][row, col]), 2)
        rows.append(result)

    out = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    ref = "zones bâties" if urban is not None else "toute la zone"
    print(f"\nPercentiles calculés parmi : {ref} (100 = plus exposé que tout le reste)")
    print(out.to_string(index=False))
    print(f"\nRésultats enregistrés : {OUT_CSV}")

    pos = out[out["flooded"] == 1]["score_moyen"]
    neg = out[out["flooded"] == 0]["score_moyen"]
    if len(pos) >= 2 and len(neg) >= 2:
        print(f"AUC (inondés vs non inondés) : {auc(pos, neg):.2f} avec {len(pos)} inondés et "
              f"{len(neg)} non inondés. Indication seulement (très peu de points).")
    else:
        print(f"{len(pos)} lieu(x) inondé(s) et {len(neg)} non inondé(s) : il faut au moins 2 de chaque "
              "pour calculer un AUC. Ajouter des points dans le CSV (flooded = 0 pour les lieux "
              "connus comme non inondés).")


if __name__ == "__main__":
    run()
