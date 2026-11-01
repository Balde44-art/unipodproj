"""Expérience d'apprentissage automatique sur les étiquettes Sentinel-1 (2024).

CE QUE CETTE EXPÉRIENCE EST ET N'EST PAS
- Elle répond à une question précise : « un modèle entraîné sur l'eau détectée par radar apporte-t-il
  quelque chose que la hauteur au-dessus du Niger (ou l'indice multicritère) ne donne pas déjà ? »
- Les étiquettes montrent l'eau fluviale et saisonnière, PAS l'inondation urbaine (voir
  flood_labels.py et docs/METHODOLOGIE.md). Le modèle prédit donc « eau fluviale détectée par radar »,
  et ne prédit pas l'inondation des quartiers. Un bon score ne valide pas une carte de risque urbain.
- Les critères hauteur et distance sont liés à la position du fleuve : s'attendre à ce qu'ils dominent.

Données
- Positifs : pixels détectés sur au moins 2 dates sur 5. Négatifs : jamais détectés. Les surfaces
  sombres toute l'année (fleuve, ombres) sont exclues (ce ne sont pas des « non inondés »).
- Variables : hauteur au-dessus du Niger, distance à l'eau, pente, TWI (+ part de bâti pour un essai).
  Aucune coordonnée n'est utilisée comme variable.

Validation SPATIALE
- La zone est découpée en blocs de BLOCK_PX x BLOCK_PX pixels (100 px = 3 km). Chaque bloc entier va dans
  le jeu d'entraînement OU dans le jeu de test (validation croisée par blocs, GroupKFold). Une validation
  aléatoire pixel par pixel serait trompeuse : deux pixels voisins se ressemblent et le modèle
  « recopierait » son voisin.
- L'AUC est calculée sur toutes les prédictions hors entraînement (agrégées), sur toute la zone et dans la
  plaine basse (hauteur <= LOW_HEIGHT_M), le test le plus sévère.

Lancement depuis la racine du projet (après flood_labels et susceptibility) :
    python -m src.models.train

Résultats : outputs/model_s1_results.csv et outputs/figures/model_s1.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.models.validation import auc

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT_CSV = ROOT / "outputs" / "model_s1_results.csv"
FIGURE = ROOT / "outputs" / "figures" / "model_s1.png"

MIN_DATES = 2
BLOCK_PX = 100
N_SPLITS = 5
LOW_HEIGHT_M = 15.0
MAX_NEG_TRAIN = 150_000
SEED = 42

FILES = {
    "hauteur": "height_above_niger_utm.tif",
    "distance": "dist_water_bamako_utm.tif",
    "pente": "slope_bamako_utm.tif",
    "twi": "twi_utm.tif",
    "bati": "built_fraction_utm.tif",
}
# Jeux de variables essayés. Chaque ligne retire ou ajoute une information pour voir ce qu'elle apporte.
FEATURE_SETS = {
    "4 critères": ["hauteur", "distance", "pente", "twi"],
    "sans hauteur": ["distance", "pente", "twi"],
    "pente + TWI seulement": ["pente", "twi"],
    "4 critères + bâti": ["hauteur", "distance", "pente", "twi", "bati"],
}


def make_gradient_boosting():
    return HistGradientBoostingClassifier(
        max_depth=4, learning_rate=0.1, max_iter=150, l2_regularization=1.0, random_state=SEED
    )


def make_logistic():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=500))


def block_ids(shape, block_px=BLOCK_PX):
    """Numéro de bloc spatial de chaque pixel (pour ne jamais séparer deux pixels voisins)."""
    rows, cols = np.indices(shape)
    n_cols = int(np.ceil(shape[1] / block_px))
    return (rows // block_px) * n_cols + (cols // block_px)


def out_of_fold_predictions(X, y, groups, make_model, n_splits=N_SPLITS, max_neg_train=MAX_NEG_TRAIN, seed=SEED):
    """Prédictions hors entraînement : chaque pixel est prédit par un modèle qui n'a vu aucun pixel de son bloc.

    L'entraînement garde tous les positifs et au plus `max_neg_train` négatifs tirés au hasard (vitesse) ;
    le test utilise TOUS les pixels du bloc écarté, donc la prévalence réelle.
    """
    rng = np.random.default_rng(seed)
    oof = np.full(len(y), np.nan, dtype="float32")
    fold_auc = []
    for train_idx, test_idx in GroupKFold(n_splits=n_splits).split(X, y, groups):
        pos = train_idx[y[train_idx] == 1]
        neg = train_idx[y[train_idx] == 0]
        if len(neg) > max_neg_train:
            neg = rng.choice(neg, max_neg_train, replace=False)
        idx = np.concatenate([pos, neg])
        model = make_model()
        model.fit(X[idx], y[idx])
        oof[test_idx] = model.predict_proba(X[test_idx])[:, 1]
        pos_test, neg_test = y[test_idx] == 1, y[test_idx] == 0
        fold_auc.append(auc(oof[test_idx][pos_test], oof[test_idx][neg_test]) if pos_test.any() else np.nan)
    return oof, fold_auc


def summarize(name, kind, scores, y, low_plain, fold_auc=None):
    """AUC et précision moyenne, sur toute la zone et dans la plaine basse."""
    row = {"variable / modèle": name, "type": kind}
    for label, mask in (("toute la zone", np.ones_like(y, bool)), ("plaine basse", low_plain)):
        pos, neg = scores[mask & (y == 1)], scores[mask & (y == 0)]
        row[f"AUC {label}"] = auc(pos, neg)
        row[f"précision moyenne {label}"] = float(average_precision_score(y[mask], scores[mask]))
    if fold_auc is not None:
        row["AUC par bloc : min"] = float(np.nanmin(fold_auc))
        row["AUC par bloc : max"] = float(np.nanmax(fold_auc))
    return row


def read(name):
    with rasterio.open(PROC / name) as src:
        arr = src.read(1).astype("float64")
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
    return arr


def run():
    feats = {k: read(f) for k, f in FILES.items()}
    count, permanent = read("flood_s1_count_utm.tif"), read("permanent_dark_utm.tif")
    baselines = {
        "hauteur seule (sans modèle)": -feats["hauteur"],
        "distance seule (sans modèle)": -feats["distance"],
        "composante fluviale (sans modèle)": read("susceptibility_fluvial_utm.tif"),
        "indice combiné (sans modèle)": read("susceptibility_bamako_utm.tif"),
    }
    shape = count.shape
    valid = np.isfinite(count) & (permanent == 0)
    for arr in feats.values():
        valid &= np.isfinite(arr)
    for arr in baselines.values():
        valid &= np.isfinite(arr)
    valid &= (count >= MIN_DATES) | (count == 0)

    y = (count[valid] >= MIN_DATES).astype("int8")
    groups = block_ids(shape)[valid]
    low_plain = feats["hauteur"][valid] <= LOW_HEIGHT_M
    print(f"{y.sum()} positifs, {(y == 0).sum()} négatifs, {len(np.unique(groups))} blocs spatiaux "
          f"de {BLOCK_PX * 30 / 1000:.0f} km de côté, validation croisée en {N_SPLITS} parties")

    rows = [summarize(name, "référence (aucun apprentissage)", arr[valid], y, low_plain)
            for name, arr in baselines.items()]
    oof_store = {}
    for set_name, cols in FEATURE_SETS.items():
        X = np.column_stack([feats[c][valid] for c in cols]).astype("float32")
        makers = {"boosting": make_gradient_boosting}
        if set_name == "4 critères":
            makers["régression logistique"] = make_logistic
        for model_name, maker in makers.items():
            oof, fold_auc = out_of_fold_predictions(X, y, groups, maker)
            label = f"{model_name} : {set_name}"
            rows.append(summarize(label, "modèle (validation spatiale)", oof, y, low_plain, fold_auc))
            oof_store[label] = oof
            print(f"  {label} : AUC {rows[-1]['AUC toute la zone']:.3f} (plaine basse {rows[-1]['AUC plaine basse']:.3f})")

    table = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 20, "display.float_format", "{:.2f}".format,
                           "display.max_colwidth", 45):
        print("\n", table.to_string(index=False))

    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(table) + 1.5))
    y_pos = np.arange(len(table))
    ax.barh(y_pos + 0.18, table["AUC toute la zone"], height=0.34, label="toute la zone")
    ax.barh(y_pos - 0.18, table["AUC plaine basse"], height=0.34, label="plaine basse (hauteur ≤ 15 m)")
    ax.axvline(0.5, color="k", ls="--", lw=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(table["variable / modèle"])
    ax.invert_yaxis()
    ax.set_xlim(0.4, 1.0)
    ax.set_xlabel("AUC (0,5 = hasard)")
    ax.set_title("Eau détectée par radar 2024 : références et modèles (validation spatiale par blocs)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    print(f"\nTableau : {OUT_CSV}\nFigure : {FIGURE}")


if __name__ == "__main__":
    run()
