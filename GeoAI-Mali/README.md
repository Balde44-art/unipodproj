# GeoAI Mali

**Geospatial Artificial Intelligence for Environmental Risk Analysis**

> **In short (EN).** A research prototype that maps where floods are most likely to hit Bamako, Mali, from open
> satellite and terrain data. It produces a *relative* exposure index (not a flood prediction) at 30 m
> resolution, checks it against radar-detected water (Sentinel-1, 2024) and six documented neighbourhoods, and
> reports honestly what is and is not validated. Full documentation is in French; code docstrings too.

**En bref (FR).** Prototype de recherche : cartographier les zones **potentiellement exposées aux
inondations autour de Bamako** à partir de données satellites et de terrain ouvertes. Le résultat est un
**indice relatif d'exposition** à 30 m (pas une prédiction d'inondation), contrôlé avec l'eau détectée par
radar en 2024 et six quartiers cités comme inondés. Les limites sont écrites à côté des résultats.

<!-- Idée : ajouter ici une capture de la carte, par exemple : ![Carte de l'indice](docs/img/carte.png) -->

---

## Par où commencer ?

| Je veux… | Je lis… |
|---|---|
| **comprendre le projet en 10 minutes** (idée, parcours, manques, pistes) | [`docs/PROJET_EXPLIQUE.md`](docs/PROJET_EXPLIQUE.md) |
| **défendre la méthode** (choix, chiffres, limites, questions du jury) | [`docs/METHODOLOGIE.md`](docs/METHODOLOGIE.md) |
| **voir les résultats pas à pas** | [`notebooks/`](notebooks/README.md) (01, 02, 03) |
| **ouvrir la carte** | `outputs/maps/susceptibility_bamako.html` après `python -m src.visualization.mapping` |
| **lancer l'application** | `streamlit run app/dashboard.py` — voir [`app/`](app/README.md) |
| **relancer tout le calcul** | le pipeline dans [`src/README.md`](src/README.md) |
| **savoir d'où viennent les données** | [`data/DATA_SOURCES.md`](data/DATA_SOURCES.md) |
| **retrouver un morceau de code** | les README de chaque dossier (ci-dessous) |

## Statut actuel

Prototype **v0.3**. Un indice relatif d'exposition (0 à 1, pixels de 30 m) construit à partir du terrain et de
l'hydrologie, avec un contrôle par radar Sentinel-1 et un contrôle sur six quartiers.

**Ce n'est pas une prédiction d'inondation.** Les poids sont des choix d'expert (testés pour leur
sensibilité, jamais ajustés sur des observations). Une expérience d'apprentissage automatique (boosting de
gradient et régression logistique, validation spatiale par blocs) a été faite sur les étiquettes radar :
elle n'apporte pas de gain décisif par rapport à la hauteur au-dessus du Niger seule (AUC 0,96 contre 0,95
à moins de 15 m du niveau du fleuve), car les seules étiquettes disponibles à grande échelle montrent l'eau
du fleuve, pas l'inondation urbaine. Elle est rapportée comme un résultat, pas retenue comme produit
principal.

### Les résultats en un coup d'œil

| Composante | Données utilisées | Contrôle |
|---|---|---|
| Fluviale | hauteur au-dessus du Niger, distance aux cours d'eau | Cohérente avec l'eau radar 2024 (AUC 0,98 ; 0,84 à moins de 15 m du niveau du fleuve). En partie circulaire. |
| Locale | pente, indice d'humidité topographique (TWI) | **Non validée** (pas d'étiquettes d'inondation urbaine). Faible face aux étiquettes fluviales. |
| Indice combiné | les quatre critères, poids égaux | 3 des 6 quartiers cités comme inondés sont dans les 20 % les plus exposés des zones bâties, 1 au 70e percentile, 2 sous la médiane |

Détails, limites et réserves : [`docs/METHODOLOGIE.md`](docs/METHODOLOGIE.md), sections 6 à 8.

## Organisation du projet

Chaque dossier a son propre README, qui explique ses fichiers, leurs entrées et leurs sorties.

```
GeoAI-Mali/
├── data/            données brutes, traitées, de référence       → data/README.md
├── src/             tout le code                                  → src/README.md
│   ├── data/            téléchargements (MNT, eau, occupation du sol, radar)   → src/data/README.md
│   ├── features/        terrain, hydrologie, indice, étiquettes radar          → src/features/README.md
│   ├── models/          contrôles et expérience d'apprentissage                → src/models/README.md
│   └── visualization/   cartes interactives                                    → src/visualization/README.md
├── notebooks/       visite guidée des résultats                   → notebooks/README.md
├── app/             tableau de bord Streamlit                     → app/README.md
├── docs/            documentation de fond                         → docs/README.md
├── outputs/         figures, cartes, tableaux de résultats (générés, non versionnés)
├── requirements.txt
└── README.md
```

## Démarrage rapide

Linux / macOS :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -c "import numpy, pandas, sklearn, geopandas, folium, streamlit; print('GeoAI Mali - Environment OK')"
```

Windows (PowerShell) : `py -3.11 -m venv .venv` puis `.\.venv\Scripts\Activate.ps1`, puis les mêmes
commandes `pip`.

Tout se lance **depuis la racine du projet** avec `python -m src.<paquet>.<script>`.

## Relancer le pipeline

Voir [`src/README.md`](src/README.md) pour le tableau complet (14 étapes, avec ce que chacune produit). En
résumé :

```bash
python -m src.data.download_dem && python -m src.features.terrain
python -m src.data.download_water && python -m src.features.water_distance
python -m src.features.hydrology
python -m src.data.download_worldcover && python -m src.features.urban_mask
python -m src.data.download_sentinel1_dea && python -m src.features.flood_labels
python -m src.features.susceptibility
python -m src.models.validate_s1 && python -m src.models.validation
python -m src.models.train                 # expérience d'apprentissage, outputs/model_s1_results.csv
python -m src.visualization.mapping        # outputs/maps/susceptibility_bamako.html
streamlit run app/dashboard.py
```

## Sources de données

Catalogue complet (licences, résolutions, limites connues) : [`data/DATA_SOURCES.md`](data/DATA_SOURCES.md).

| Donnée | Rôle | Statut |
|---|---|---|
| Copernicus DEM GLO-30 | Altitude, pente, hydrologie (TWI) | **Utilisée** |
| OpenStreetMap (Overpass) | Cours d'eau, référence du Niger | **Utilisée** |
| ESA WorldCover 2021 | Masque des zones bâties (comparaison seulement) | **Utilisée** |
| Sentinel-1 RTC (Digital Earth Africa `s1_rtc`) | Étiquettes d'eau, saison des pluies 2024 (contrôle de cohérence) | **Utilisée** |
| Quartiers de référence (articles, presse, mémoire) | Contrôle sur des cas, 6 lieux | **Utilisée** (`data/reference/flood_reference_points.csv`) |
| HydroSHEDS, CHIRPS, Sentinel-2 | Pas nécessaires jusqu'ici | Identifiées, non utilisées |
| Étiquettes d'inondation urbaine | Variable cible | **Problème ouvert** : aucune emprise ouverte trouvée pour Bamako |

Données © contributeurs OpenStreetMap (ODbL) ; contient des données modifiées Copernicus Sentinel ;
ESA WorldCover 2021 (CC BY 4.0). Vérifier les licences avant toute diffusion hors du mémoire.

## Technologies

Python 3.11 · NumPy, pandas · GeoPandas, Rasterio · scikit-learn · Folium · Streamlit

## Principe de recherche

Tous les résultats sont documentés, les limites sont écrites à côté des résultats, et toute donnée
synthétique serait clairement distinguée des observations réelles (aucune n'est utilisée dans les résultats
présentés).

## Limites principales

Pas d'étiquettes d'inondation urbaine ni de vérité terrain ; composante locale non validée ; drainage
artificiel absent ; modèle d'altitude de surface (bâtiments inclus) ; une seule saison radar (2024) ; poids
choisis à la main. La liste complète et les pistes pour la suite sont dans
[`docs/PROJET_EXPLIQUE.md`](docs/PROJET_EXPLIQUE.md), sections 5 et 6.
