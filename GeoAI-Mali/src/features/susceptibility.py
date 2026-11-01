"""Indice de susceptibilité (version 0.3) : combinaison multicritère SANS apprentissage supervisé.

Ce n'est PAS une prédiction d'inondation. C'est un indice relatif entre 0 et 1 qui classe les
pixels de la zone d'étude selon leur exposition potentielle au débordement du fleuve et à
l'accumulation d'eau, d'après quatre critères de terrain.

Critères :
    height    hauteur au-dessus du Niger            petite valeur = plus exposé
              (data/processed/height_above_niger_utm.tif)
    distance  distance au cours d'eau le plus proche  petite valeur = plus exposé
              (data/processed/dist_water_bamako_utm.tif)
    slope     pente                                  petite valeur = plus exposé
              (data/processed/slope_bamako_utm.tif)
    twi       indice d'humidité topographique        GRANDE valeur = plus exposé
              (data/processed/twi_utm.tif ; python -m src.features.hydrology)
              Mesure où l'eau converge (cuvettes, bas-fonds), même loin du fleuve.

Méthode :
1. Chaque critère est ramené entre 0 et 1 par son RANG (percentile dans la zone d'étude).
   Un indice de 0,7 signifie donc « en moyenne parmi les ~30 % de pixels les plus exposés »,
   et non une probabilité d'inondation. Un premier essai en min-max linéaire donnait 60 % des
   pixels au-dessus de 0,7 (échelle saturée) : abandonné.
2. L'indice est la somme pondérée des critères. Plusieurs jeux de poids sont testés.
3. Analyse de sensibilité : 100 jeux de poids tirés au hasard (loi de Dirichlet uniforme sur
   toutes les combinaisons de poids possibles). Pour chaque pixel, on calcule la fraction des
   tirages où il fait partie des 20 % de pixels les plus exposés. Un pixel proche de 1 est
   « robustement exposé », quel que soit le choix des poids.

Deux composantes lisibles (v0.3) : l'indice combiné est complété par deux sous-indices.
    fluviale  = moyenne des rangs de height et distance  (débordement du fleuve et du réseau)
    locale    = moyenne des rangs de slope et twi         (ruissellement, cuvettes, eau qui converge)
Pourquoi : le contrôle Sentinel-1 2024 (python -m src.models.validate_s1) ne voit que l'eau
fluviale. Il valide donc (en partie) la composante fluviale, et ne peut rien dire de la composante
locale, qui reste NON validée faute d'étiquettes d'inondation urbaine. Les présenter séparément
évite qu'un bon résultat fluvial serve de caution à la partie ruissellement. Les poids de
l'indice combiné n'ont PAS été ajustés sur ces étiquettes.

Historique : la v0.1 (3 critères, sans TWI) plaçait Missabougou au percentile ~87 des zones
bâties. Le TWI a été ajouté parce que ce quartier est décrit comme un réceptacle du
ruissellement, ce que la v0.1 ne représentait pas.

Limites à rappeler dans le mémoire :
- Les poids sont des choix d'expert, pas appris sur des données. D'où l'analyse de sensibilité.
- Aucune validation sur des inondations observées en dehors d'un quartier pour l'instant.
- Le TWI vient d'un modèle de surface (bâtiments et arbres inclus) : il est bruité en ville.
- Ne représente pas le drainage artificiel (caniveaux, collecteurs).

Lancement depuis la racine du projet :
    python -m src.features.susceptibility
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
PATHS = {
    "height": PROCESSED / "height_above_niger_utm.tif",
    "distance": PROCESSED / "dist_water_bamako_utm.tif",
    "slope": PROCESSED / "slope_bamako_utm.tif",
    "twi": PROCESSED / "twi_utm.tif",
}
OUT_SCORE = PROCESSED / "susceptibility_bamako_utm.tif"
OUT_ROBUST = PROCESSED / "susceptibility_robust_utm.tif"
OUT_FLUVIAL = PROCESSED / "susceptibility_fluvial_utm.tif"
OUT_LOCAL = PROCESSED / "susceptibility_local_utm.tif"
FIGURE = ROOT / "outputs" / "figures" / "susceptibility_bamako.png"

CRITERIA = ["height", "distance", "slope", "twi"]
HIGH_IS_RISKY = {"twi"}  # pour les autres critères, une petite valeur est à risque

SCENARIOS = {
    "poids_egaux": {"height": 0.25, "distance": 0.25, "slope": 0.25, "twi": 0.25},
    "fleuve_dominant": {"height": 0.40, "distance": 0.20, "slope": 0.15, "twi": 0.25},
    "reseau_dominant": {"height": 0.15, "distance": 0.40, "slope": 0.20, "twi": 0.25},
    "relief_dominant": {"height": 0.20, "distance": 0.15, "slope": 0.35, "twi": 0.30},
    "convergence_dominante": {"height": 0.20, "distance": 0.20, "slope": 0.10, "twi": 0.50},
}
MAIN_SCENARIO = "poids_egaux"
COMPONENTS = {
    "fluviale": {"height": 0.5, "distance": 0.5},
    "locale": {"slope": 0.5, "twi": 0.5},
}


def component_score(layers, weights):
    """Moyenne pondérée des seuls critères d'une composante (NaN là où une couche est vide)."""
    total = sum(weights.values())
    return sum(w / total * layers[k] for k, w in weights.items()).astype("float32")


def normalize_low_is_risky(arr):
    """Normalisation par le rang : 0 = peu exposé, 1 = très exposé (petites valeurs = à risque).

    Chaque pixel reçoit son percentile parmi tous les pixels valides de la zone : la plus petite
    valeur donne un score proche de 1, la plus grande un score proche de 0, et la médiane 0,5.
    Contrairement à un min-max linéaire, le résultat ne dépend pas de la forme de la
    distribution (très asymétrique ici : la plupart des pixels ont de petites valeurs de
    distance, de pente et de hauteur, ce qui poussait presque tout vers un score élevé).
    Contrepartie : seule la position relative compte, pas l'écart réel (10 m ou 50 m au-dessus
    du fleuve comptent par leur rang).
    """
    valid = ~np.isnan(arr)
    if np.nanmax(arr) <= np.nanmin(arr):
        raise ValueError("Critère sans variation : normalisation impossible.")
    ranks = rankdata(arr[valid], method="average")  # rang moyen en cas d'égalité
    out = np.full(arr.shape, np.nan, dtype="float32")
    out[valid] = 1.0 - (ranks - 0.5) / valid.sum()
    return out


def normalize_high_is_risky(arr):
    """Même principe, pour un critère où les GRANDES valeurs sont à risque (ex. TWI)."""
    return normalize_low_is_risky(-arr)


def normalize(name, arr):
    return normalize_high_is_risky(arr) if name in HIGH_IS_RISKY else normalize_low_is_risky(arr)


def weighted_score(layers, weights):
    """Somme pondérée des critères normalisés (NaN là où une couche est vide)."""
    total = sum(weights[k] for k in CRITERIA)
    score = sum(weights[k] / total * layers[k] for k in CRITERIA)
    return score.astype("float32")


def robustness(layers, n_draws=100, top_fraction=0.2, seed=42):
    """Fraction des tirages de poids où le pixel est dans les `top_fraction` plus exposés."""
    rng = np.random.default_rng(seed)
    stack = np.stack([layers[k] for k in CRITERIA])
    valid = ~np.isnan(stack).any(axis=0)
    values = stack[:, valid]
    counts = np.zeros(values.shape[1], dtype="int32")
    for _ in range(n_draws):
        weights = rng.dirichlet(np.ones(len(CRITERIA)))
        score = weights @ values
        counts += score >= np.quantile(score, 1 - top_fraction)
    out = np.full(valid.shape, np.nan, dtype="float32")
    out[valid] = counts / n_draws
    return out


def run():
    raw, profile = {}, None
    for name, path in PATHS.items():
        if not path.exists():
            raise FileNotFoundError(
                f"{path.name} introuvable. Lancer d'abord : "
                + ("python -m src.features.hydrology" if name == "twi" else "les étapes précédentes")
            )
        with rasterio.open(path) as src:
            raw[name] = src.read(1)
            if profile is None:
                profile = src.profile.copy()
    shapes = {a.shape for a in raw.values()}
    if len(shapes) != 1:
        raise RuntimeError(f"Les couches n'ont pas la même grille : {shapes}")

    layers = {k: normalize(k, v) for k, v in raw.items()}

    scores = {name: weighted_score(layers, w) for name, w in SCENARIOS.items()}
    main = scores[MAIN_SCENARIO]
    robust = robustness(layers)

    fluvial = component_score(layers, COMPONENTS["fluviale"])
    local = component_score(layers, COMPONENTS["locale"])

    for path, arr in ((OUT_SCORE, main), (OUT_ROBUST, robust), (OUT_FLUVIAL, fluvial), (OUT_LOCAL, local)):
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(arr, 1)

    valid = ~np.isnan(main)
    print(f"Indice v0.3 (poids égaux) : médiane {np.nanmedian(main):.2f} | "
          f"{100 * np.nanmean(main > 0.7):.1f} % des pixels au-dessus de 0,7")

    stack = np.stack([layers[k][valid] for k in CRITERIA])
    corr = np.corrcoef(stack)
    print("Corrélation entre critères (rangs) :")
    for i, a in enumerate(CRITERIA):
        for j in range(i + 1, len(CRITERIA)):
            print(f"  {a} / {CRITERIA[j]} : {corr[i, j]:+.2f}")

    print("Corrélation entre scénarios de poids (1 = cartes identiques) :")
    ref = scores[MAIN_SCENARIO][valid]
    for name, arr in scores.items():
        if name != MAIN_SCENARIO:
            print(f"  {MAIN_SCENARIO} vs {name} : {np.corrcoef(ref, arr[valid])[0, 1]:.3f}")
    print(f"Composantes : corrélation fluviale / locale = {np.corrcoef(fluvial[valid], local[valid])[0, 1]:+.2f} "
          f"(proche de 0 = elles apportent des informations différentes)")
    top_main = main >= np.nanquantile(main, 0.8)
    print(f"Robustesse : {100 * np.nanmean(robust >= 0.9):.1f} % des pixels sont dans le top 20 % "
          f"dans au moins 90 % des tirages ; "
          f"{100 * np.nanmean(robust[top_main] >= 0.9):.0f} % du top 20 % de la carte principale l'est aussi")

    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.ravel()
    panels = [
        (main, "YlOrRd", "Indice combiné v0.3 (0 à 1)\nrelatif, pas une prédiction"),
        (robust, "Blues", "Robustesse : part des tirages de poids\noù le pixel est dans le top 20 %"),
        (fluvial, "YlOrRd", "Composante fluviale (hauteur + distance)\ncontrôlée en partie par Sentinel-1"),
        (local, "YlOrRd", "Composante locale (pente + TWI)\nNON validée (pas d'étiquettes urbaines)"),
    ]
    for ax, (arr, cmap, title) in zip(axes, panels):
        im = ax.imshow(arr, cmap=cmap, vmin=0, vmax=1)
        ax.set_title(title)
        fig.colorbar(im, ax=ax, shrink=0.8)
    for ax in axes:
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    print(f"Figure enregistrée : {FIGURE}")


if __name__ == "__main__":
    run()
