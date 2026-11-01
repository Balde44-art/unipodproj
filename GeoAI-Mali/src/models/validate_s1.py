"""Contrôle de l'indice multicritère avec les zones d'eau détectées par Sentinel-1 en 2024.

Question posée : les pixels où le fleuve est sorti de son lit en 2024 ont-ils un score d'indice plus
élevé que les autres pixels ?

CE QUE CE CONTRÔLE VAUT (à écrire tel quel dans le mémoire) :
- Les étiquettes sont dérivées d'un capteur (pas de vérité terrain) et ne montrent QUE l'eau fluviale
  et saisonnière (voir flood_labels.py). L'inondation urbaine n'y est quasiment pas présente.
- Deux critères de l'indice (hauteur au-dessus du Niger, distance à l'eau) sont liés à la position
  du fleuve : un bon score global est donc ATTENDU et ne prouve pas à lui seul que l'indice prédit
  l'inondation. Le contrôle « dans la plaine basse seulement » (hauteur <= LOW_HEIGHT_M) est plus
  sévère : il compare des pixels déjà proches du fleuve en altitude.
- Les pixels voisins se ressemblent : l'AUC est une mesure descriptive, pas un test statistique.
- Positifs = inondés sur au moins 2 dates sur 5 (eau durable, moins de bruit) ; négatifs = jamais
  détectés, hors surfaces sombres toute l'année (fleuve, ombres : ce ne sont pas des « non inondés »).
- Un négatif signifie « pas détecté par le radar », PAS « jamais inondé ».

Lancement depuis la racine du projet (après flood_labels) :
    python -m src.models.validate_s1

Résultats : outputs/validation_s1.csv et outputs/figures/validation_s1.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

from src.models.validation import auc

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT_CSV = ROOT / "outputs" / "validation_s1.csv"
FIGURE = ROOT / "outputs" / "figures" / "validation_s1.png"

MIN_DATES = 2
LOW_HEIGHT_M = 15.0
TOP_FRACTIONS = (0.1, 0.2, 0.3)

# Critère -> (fichier, signe : +1 si une valeur haute = plus risqué)
CRITERIA = {
    "height": ("height_above_niger_utm.tif", -1),
    "distance": ("dist_water_bamako_utm.tif", -1),
    "slope": ("slope_bamako_utm.tif", -1),
    "twi": ("twi_utm.tif", +1),
}


def evaluate(score, positive, negative, top_fractions=TOP_FRACTIONS):
    """AUC et part des positifs dans les X % de pixels les plus élevés (calculés sur pos + neg)."""
    pos, neg = score[positive], score[negative]
    out = {"n_pos": int(pos.size), "n_neg": int(neg.size), "auc": auc(pos, neg) if pos.size and neg.size else np.nan}
    pool = np.concatenate([pos, neg])
    for f in top_fractions:
        threshold = np.quantile(pool, 1 - f)
        out[f"positifs_dans_top{int(f * 100)}pct"] = float(np.mean(pos >= threshold)) if pos.size else np.nan
    return out


def read(name):
    with rasterio.open(PROC / name) as src:
        arr = src.read(1).astype("float64")
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
    return arr


def run():
    score = read("susceptibility_bamako_utm.tif")
    count = read("flood_s1_count_utm.tif")
    permanent = read("permanent_dark_utm.tif")
    height = read("height_above_niger_utm.tif")
    urban = read("urban_mask_utm.tif") > 0

    valid = np.isfinite(score) & np.isfinite(count) & (permanent == 0)
    positive = valid & (count >= MIN_DATES)
    negative = valid & (count == 0)
    print(f"Positifs (inondés sur >= {MIN_DATES} dates) : {positive.sum()} pixels ; "
          f"négatifs (jamais détectés, hors eau permanente) : {negative.sum()} pixels")

    rows = []
    strata = {
        "toute la zone": (positive, negative),
        f"plaine basse (hauteur <= {LOW_HEIGHT_M:.0f} m)": (positive & (height <= LOW_HEIGHT_M),
                                                          negative & (height <= LOW_HEIGHT_M)),
        "zone bâtie seulement": (positive & urban, negative & urban),
        "hors zone bâtie": (positive & ~urban, negative & ~urban),
    }
    layers = {"indice multicritère": score}
    for label, file in (("composante fluviale", "susceptibility_fluvial_utm.tif"),
                        ("composante locale", "susceptibility_local_utm.tif")):
        if (PROC / file).exists():
            layers[label] = read(file)
        else:
            print(f"({file} absent : relancer python -m src.features.susceptibility)")
    for variable, layer in layers.items():
        for label, (pos, neg) in strata.items():
            pos, neg = pos & np.isfinite(layer), neg & np.isfinite(layer)
            row = {"strate": label, "variable": variable}
            row.update(evaluate(layer, pos, neg))
            rows.append(row)

    # Chaque critère seul (même strates) : montre d'où vient le pouvoir de discrimination
    for name, (file, sign) in CRITERIA.items():
        values = sign * read(file)
        values[~np.isfinite(values)] = np.nan
        for label, (pos, neg) in strata.items():
            pos, neg = pos & np.isfinite(values), neg & np.isfinite(values)
            row = {"strate": label, "variable": f"critère seul : {name}"}
            row.update(evaluate(values, pos, neg))
            rows.append(row)

    table = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.float_format", "{:.2f}".format):
        print("\n", table.drop(columns=[]).to_string(index=False))

    # Figure : distribution du score et part des positifs retrouvés
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    bins = np.linspace(0, 1, 41)
    axes[0].hist(score[negative], bins=bins, density=True, alpha=0.6, label="jamais détecté (négatifs)")
    axes[0].hist(score[positive], bins=bins, density=True, alpha=0.6, label=f"inondé >= {MIN_DATES} dates (positifs)")
    axes[0].set_xlabel("Score de l'indice multicritère")
    axes[0].set_ylabel("Densité")
    axes[0].set_title("Distribution du score")
    axes[0].legend()

    pool = np.concatenate([score[positive], score[negative]])
    thresholds = np.quantile(pool, np.linspace(0, 1, 101))
    recall = [np.mean(score[positive] >= t) for t in thresholds]
    share = 1 - np.linspace(0, 1, 101)
    axes[1].plot(share * 100, np.array(recall) * 100, label="indice")
    axes[1].plot([0, 100], [0, 100], "k--", label="hasard")
    axes[1].set_xlabel("% de pixels les plus élevés de l'indice")
    axes[1].set_ylabel("% des pixels inondés retrouvés")
    axes[1].set_title("Courbe de gain")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    print(f"\nTableau : {OUT_CSV}\nFigure : {FIGURE}")


if __name__ == "__main__":
    run()
