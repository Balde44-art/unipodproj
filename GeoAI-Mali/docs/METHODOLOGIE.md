# GeoAI Mali — Note de méthode

*Version 0.3 — prototype de cartographie des zones potentiellement exposées aux inondations autour de Bamako.*

## 0. L'essentiel en dix lignes

- Le projet produit un **indice relatif de susceptibilité** (0 à 1) sur une zone de ~30 x 30 km autour de Bamako, à 30 m de résolution. **Ce n'est pas une prédiction d'inondation** : un pixel à 0,7 se lit « parmi les ~30 % de pixels les plus exposés de la zone », pas « 70 % de chances d'être inondé ».
- L'indice combine **quatre critères de terrain** : hauteur au-dessus du Niger, distance au cours d'eau le plus proche, pente, indice d'humidité topographique (TWI). Il est présenté en **deux composantes** : *fluviale* (hauteur + distance) et *locale* (pente + TWI).
- Les poids sont des **choix d'expert**, testés par analyse de sensibilité. Ils n'ont **pas** été ajustés sur des observations.
- Un contrôle avec des images radar Sentinel-1 (saison des pluies 2024) valide en partie la composante **fluviale** (AUC 0,98 sur toute la zone, 0,84 en plaine basse). La composante **locale** n'est **pas validée** : il n'existe pas d'étiquettes d'inondation urbaine ouvertes pour Bamako.
- Un **modèle d'apprentissage automatique a été testé** (validation spatiale par blocs) : il n'apporte pas de gain décisif par rapport à la hauteur au-dessus du fleuve, car les étiquettes décrivent le fleuve. Il n'est pas retenu comme résultat principal (section 7).

## 1. Question posée et périmètre

**Question** : où, autour de Bamako, le relief et le réseau hydrographique rendent-ils une zone plus exposée au débordement du fleuve et à l'accumulation d'eau ?

**Ce que le projet fait** : classe les pixels les uns par rapport aux autres.
**Ce qu'il ne fait pas** : prédire une date, une hauteur d'eau, un nombre de personnes touchées, ni représenter le drainage artificiel (caniveaux, collecteurs, ouvrages).

**Zone d'étude** : longitude -8,15 à -7,85, latitude 12,50 à 12,80 (environ 33 x 33 km), reprojetée en UTM zone 29N (EPSG:32629), pixels de 30 m, grille de 1080 x 1080.

## 2. Données utilisées

| Donnée | Source | Usage | Remarque |
|---|---|---|---|
| Modèle numérique de terrain | Copernicus DEM GLO-30 (tuiles COG sur AWS) | altitude, pente, hydrologie | C'est un modèle de **surface** (bâtiments et arbres inclus), donc bruité en ville |
| Réseau hydrographique | OpenStreetMap (API Overpass) | distance au cours d'eau, repérage du Niger | 883 objets, 1042 segments, représentés par des lignes ; incomplet |
| Occupation du sol | ESA WorldCover 2021 v200 (10 m) | masque des zones bâties (classe 50) | Seuil de 25 % de bâti, dilatation de 3 pixels ; 49 % de la zone est « bâtie » |
| Radar | Digital Earth Africa `s1_rtc` (Sentinel-1, ~20 m, VV/VH linéaire) | étiquettes d'eau pour le contrôle | Orbite 16 ascendante, une image tous les 12 jours |
| Lieux de référence | Articles, presse, mémoires (liste dans `data/reference/flood_reference_points.csv`) | contrôle ponctuel | 7 quartiers cités, 1 seul localisé à ce jour (Missabougou) |

Les sources détaillées et les points encore à vérifier sont dans `data/DATA_SOURCES.md`.

**Données synthétiques** : aucune n'est utilisée dans les résultats présentés ici.

## 3. Construction des critères

1. **Altitude et pente.** Le MNT est reprojeté en UTM (30 m, interpolation bilinéaire). La pente vient du gradient de l'altitude (`numpy.gradient`).
   *Incident corrigé* : une ligne de zéros issue de l'assemblage des tuiles produisait une altitude minimale de 0 m et une pente de 85°. Elle est maintenant traitée comme donnée manquante (altitude minimale 304 m, pente maximale 48°).
2. **Hauteur au-dessus du Niger.** Pour chaque pixel, altitude moins l'altitude du Niger le plus proche (filtre minimum de 5 pixels sur le lit du fleuve). Le Niger seul est utilisé comme référence : l'utiliser avec tous les petits cours d'eau OSM faisait apparaître des facettes artificielles.
3. **Distance au cours d'eau le plus proche** (réseau OSM complet, en mètres).
4. **TWI (indice d'humidité topographique)** : `ln(a / tan β)`, avec `a` la surface drainée par unité de largeur et `β` la pente (plancher de 0,5°). Il se calcule en trois étapes, toutes en NumPy pur :
   - remplissage des dépressions (Priority-Flood avec epsilon) ;
   - directions d'écoulement D8 ;
   - accumulation des écoulements.

   Sur la zone, 1,9 % des pixels sont relevés de plus de 0,5 m par le remplissage (maximum 7,2 m), et la médiane du TWI est de 7,7. Le TWI est le critère le plus fragile : il hérite du bruit du modèle de surface.

## 4. L'indice multicritère

**Normalisation par le rang.** Chaque critère est transformé en percentile sur la zone : 1 = très exposé, 0 = peu exposé, 0,5 = médiane. Hauteur, distance et pente : petite valeur = exposé. TWI : grande valeur = exposé.
*Pourquoi pas min-max ?* Un premier essai en min-max donnait une médiane de 0,77 et 60 % des pixels au-dessus de 0,7 : l'échelle était saturée, car la plupart des pixels ont de petites valeurs de distance, de pente et de hauteur. Le rang corrige cela (médiane 0,51, 17 % au-dessus de 0,7). Contrepartie : seule la position relative compte, pas l'écart réel.

**Combinaison.** Somme pondérée. Scénario principal : poids égaux (0,25 chacun).

**Composantes** (ajoutées en v0.3) :
- fluviale = moyenne des rangs de *hauteur* et *distance* ;
- locale = moyenne des rangs de *pente* et *TWI*.

Corrélation entre composantes : +0,28 (elles apportent des informations en partie différentes). Corrélations entre critères : pente/TWI +0,61, hauteur/pente +0,52, hauteur/distance +0,47, hauteur/TWI +0,28, distance/pente +0,06, distance/TWI +0,02.

## 5. Sensibilité aux choix de poids

- **Cinq scénarios de poids** (égaux, fleuve dominant, réseau dominant, relief dominant, convergence dominante) donnent des cartes très proches du scénario principal : corrélations de 0,95 à 0,99.
- **Analyse de Monte Carlo** : 100 jeux de poids tirés au hasard (loi de Dirichlet uniforme). Pour chaque pixel, on regarde la fraction des tirages où il est dans les 20 % les plus exposés. Résultat : 7,6 % des pixels sont dans ce top 20 % dans au moins 90 % des tirages, et 38 % du top 20 % de la carte principale l'est aussi.

**Lecture** : le choix des poids change peu la carte d'ensemble, mais seule une minorité de pixels est classée « très exposée » quels que soient les poids. Cette minorité est la zone à présenter comme la plus fiable.

## 6. Contrôles par les observations

### 6.1 Étiquettes Sentinel-1 (2024)

**Méthode.** Détection de changement. Pour chacune des 5 dates de la saison des pluies (14 et 26 août, 7 et 19 septembre, 1er octobre 2024), un pixel est marqué « eau nouvelle » s'il est :
- sombre (VV < -18 dB) ;
- en baisse d'au moins 3 dB par rapport à la référence sèche (médiane de 3 images de mars-avril 2024, même orbite) ;
- non sombre en saison sèche (on retire fleuve, routes goudronnées, ombres radar) ;
- dans un groupe d'au moins 8 pixels connectés.

Les masques sont ramenés sur la grille de 30 m (part inondée ≥ 30 %), et les pentes de plus de 8° sont exclues. Les seuils sont des valeurs usuelles de la littérature, **non calibrées sur Bamako**.

**Ce qu'on trouve.** L'eau nouvelle passe de 6,6 km² (14 août) à 13,1 km² (1er octobre) ; 16,2 km² sont détectés au moins une fois et 14,3 km² au moins deux fois. Les pixels détectés suivent le lit du Niger : il s'agit de la **montée du fleuve et de sa plaine d'inondation**. Seulement 6 % sont en zone bâtie, alors que celle-ci couvre 49 % de la carte.

**Ce que cela implique.** Le radar ne voit pas l'inondation urbaine (double rebond entre les bâtiments, eau sous 12 jours entre deux images). Ces étiquettes **ne représentent pas le risque d'inondation urbaine**.

### 6.2 Test de l'indice contre ces étiquettes

Positifs = pixels inondés sur au moins 2 dates (14 871). Négatifs = pixels jamais détectés, hors surfaces sombres toute l'année (1 165 055). AUC = probabilité qu'un pixel inondé ait un score plus élevé qu'un pixel non détecté.

| Variable | AUC, toute la zone | AUC, plaine basse (hauteur ≤ 15 m) |
|---|---|---|
| Indice combiné | 0,93 | 0,71 |
| Composante fluviale | 0,98 | 0,84 |
| Composante locale | 0,71 | 0,59 |
| Hauteur seule | 1,00 | 0,95 |
| Distance seule | 0,93 | 0,77 |
| Pente seule | 0,73 | 0,60 |
| TWI seul | 0,64 | 0,57 |

**Lecture honnête :**
- Les pixels détectés sont par construction ceux que le fleuve vient de couvrir, donc ceux qui sont tout juste au-dessus du niveau de l'eau. La hauteur au-dessus du Niger les sépare parfaitement (AUC 1,00) : **ce résultat est circulaire**. Le test confirme que l'indice sait où est le fleuve.
- Le test « plaine basse » est plus sévère, car il compare des pixels déjà proches du fleuve en altitude. La composante fluviale y garde 0,84.
- La composante locale est faible (0,59 en plaine basse). Le 0,71 global vient en partie de sa corrélation avec la hauteur. **Cela ne démontre pas qu'elle est inutile** : ces étiquettes ne contiennent pas d'inondation par ruissellement, donc elles ne peuvent ni la confirmer ni l'infirmer.
- L'indice combiné fait moins bien que sa meilleure variable (0,93 contre 1,00). Les poids n'ont **pas** été modifiés pour améliorer ce chiffre : ce serait ajuster l'indice sur des étiquettes qui ne représentent que le fleuve.
- L'AUC est une mesure descriptive. Les pixels voisins se ressemblent, donc on ne peut pas lui associer un test de significativité.

### 6.3 Quartiers de référence

Six quartiers cités comme inondés dans la littérature ou la presse sont localisés (clic au centre du quartier sur imagerie satellite, disque de 500 à 600 m). Pour chacun, on calcule le score moyen du disque et son percentile parmi les pixels de zone bâtie (100 = plus exposé que tout le reste de la zone bâtie).

| Quartier | Score moyen | Percentile (zones bâties) | Hauteur | Distance | Pente | TWI |
|---|---|---|---|---|---|---|
| Missabougou | 0,70 | 84 | 90 | 85 | 43 | 44 |
| Niamakoro | 0,73 | 92 | 61 | 87 | 86 | 86 |
| Banconi | 0,72 | 90 | 82 | 97 | 54 | 45 |
| Kalabambougou | 0,66 | 70 | 82 | 21 | 93 | 87 |
| Lafiabougou | 0,56 | 44 | 65 | 17 | 57 | 49 |
| Taliko | 0,56 | 43 | 60 | 80 | 17 | 18 |

**Lecture :**
- Trois quartiers sont bien classés (84 à 92), un est au 70e percentile et deux sont **sous la médiane** (43 à 44). Le percentile moyen est d'environ 70, contre 50 attendu au hasard. C'est un signal en faveur de l'indice, **pas une validation** : six points, choisis parce qu'ils sont célèbres pour avoir été inondés, voisins entre eux, sans aucun lieu non inondé pour comparer. L'AUC est impossible à calculer.
- Les deux quartiers mal classés (Lafiabougou, Taliko) sont à l'ouest, loin du réseau OSM (Lafiabougou : percentile de distance 17) ou en pente (Taliko : pente 17, TWI 18). Les hypothèses à examiner, **non vérifiées**, sont : inondation par ruissellement et débordement du drainage artificiel, absent du modèle ; canaux ou marigots absents d'OSM ; bruit du modèle de surface ; point trop approximatif (un quartier fait 1 à 2 km et l'eau n'en touche qu'une partie).
- Kalabambougou est décrit comme riverain du Niger, mais son percentile de distance est de 21 : à vérifier sur la carte (position du clic, réseau OSM).
- Aucun poids n'a été ajusté pour améliorer ces chiffres : cela reviendrait à régler l'indice sur six points.

## 7. Expérience d'apprentissage automatique

**Question** : un modèle entraîné sur les étiquettes Sentinel-1 apporte-t-il quelque chose que la hauteur au-dessus du Niger, ou l'indice multicritère, ne donne pas déjà ?

**Protocole** (`python -m src.models.train`)
- Cible : pixel détecté inondé sur au moins 2 dates (14 871 positifs, environ 1,18 million de négatifs).
- Variables : hauteur, distance, pente, TWI (et, pour un essai, la part de bâti). Aucune coordonnée.
- Modèles : boosting de gradient (profondeur 4, 150 itérations) et régression logistique.
- **Validation spatiale** : la zone est découpée en blocs de 3 km, chaque bloc entier est soit en entraînement, soit en test (validation croisée en 5 parties). Les scores sont calculés sur les prédictions hors entraînement, sur tous les pixels des blocs écartés.
- Références sans apprentissage : hauteur seule, distance seule, composante fluviale, indice combiné.

**Résultats**

| Variable ou modèle | AUC toute la zone | AUC plaine basse | Précision moyenne |
|---|---|---|---|
| Hauteur seule (sans modèle) | 0,996 | 0,952 | 0,63 |
| Distance seule (sans modèle) | 0,933 | 0,770 | 0,10 |
| Composante fluviale (sans modèle) | 0,985 | 0,841 | 0,38 |
| Indice combiné (sans modèle) | 0,926 | 0,705 | 0,25 |
| Régression logistique, 4 critères | 0,996 | 0,955 | 0,65 |
| Boosting, 4 critères | 0,997 | 0,960 | 0,70 |
| Boosting, 4 critères + bâti | 0,997 | 0,965 | 0,72 |
| Boosting, sans la hauteur | 0,954 | 0,821 | 0,24 |
| Boosting, pente + TWI seulement | 0,713 | 0,588 | 0,11 |

Les AUC des cinq parties du boosting à 4 critères sont comprises entre 0,996 et 0,999 ; celles de « pente + TWI seulement » entre 0,60 et 0,79 (le résultat dépend beaucoup du secteur testé).

**Lecture**
- **Aucun gain décisif.** L'AUC passe de 0,952 (hauteur seule) à 0,960 (boosting) en plaine basse. La précision moyenne monte un peu (0,63 à 0,70), ce qui indique que le modèle classe un peu mieux les pixels les plus exposés, mais la différence reste modeste et on ne peut pas lui associer d'intervalle de confiance.
- **La régression logistique fait presque aussi bien que le boosting** : la relation est simple, un modèle complexe n'est pas nécessaire.
- **Pente et TWI ne rendent pas l'eau fluviale prévisible** : même appris, ils plafonnent à 0,59 en plaine basse, soit le score de la composante locale à poids égaux. Ils ajoutent un peu d'information à la distance (0,77 → 0,82 sans la hauteur), pas plus que la composante fluviale (0,84).
- **Le bâti apporte presque rien** (+0,005 d'AUC), et il est probablement lié à la position du fleuve (on ne bâtit pas dans le lit).

**Ce que cela signifie**
- Les étiquettes décrivent le fleuve : un modèle y retrouve la hauteur au-dessus de l'eau, et rien de plus. Les scores très élevés ne sont pas une preuve de qualité pour la cartographie du risque urbain.
- Le modèle prédit « eau fluviale détectée par radar en 2024 », pas l'inondation des quartiers. **On ne le retient donc pas comme résultat principal** ; l'indice multicritère, transparent et testé en sensibilité, reste le livrable.
- La conclusion tient aux étiquettes, pas à la méthode : avec des emprises d'inondation en ville et des lieux non inondés connus, on pourrait refaire la même expérience avec le même protocole (validation par blocs, comparaison à une référence simple).

**Limites propres à l'expérience** : pas de recherche d'hyperparamètres (valeurs fixées a priori) ; une seule saison ; étiquettes dérivées d'un capteur ; la validation par blocs de 3 km limite, sans supprimer, la ressemblance entre pixels voisins ; l'AUC est descriptive.

## 8. Limites

- **Pas de vérité terrain** : aucune des étiquettes n'est vérifiée sur le terrain.
- **Modèle de surface** : le MNT inclut bâtiments et arbres. Pente, TWI et hydrologie sont bruités en ville.
- **OSM incomplet** : le réseau hydrographique et surtout les canaux urbains sont partiels. Le drainage artificiel n'est pas représenté.
- **Radar** : mauvais en ville dense, échantillonné tous les 12 jours (les pics sont manqués). Seuils non calibrés.
- **Poids** : choix d'expert, non appris.
- **Un seul point localisé** pour le contrôle urbain, et aucun négatif.
- **Résolution** : 30 m, trop grossier pour une rue ou une parcelle.
- **Une seule saison** : 2024 uniquement pour le radar.

## 9. Questions probables du jury

**« Pourquoi une somme pondérée plutôt qu'un modèle ? »** Parce qu'il n'existe pas d'étiquettes qui représentent ce qu'on cherche. L'indice est transparent, chaque critère se lit sur une carte, et on évite un modèle qui aurait l'air précis sans l'être.

**« Comment avez-vous choisi les poids ? »** Poids égaux par défaut (aucune raison de privilégier un critère), puis test de cinq scénarios et de 100 tirages aléatoires. Les cartes restent très proches (corrélation 0,95 à 0,99).

**« Votre indice est-il validé ? »** En partie. La composante fluviale est cohérente avec l'eau détectée par radar en 2024 (AUC 0,98 ; 0,84 en plaine basse), mais ce test est en partie circulaire. La composante locale n'est pas validée.

**« Pourquoi le radar ne suffit-il pas ? »** Il voit l'eau libre et large, pas l'eau entre les bâtiments. 6 % seulement des pixels détectés sont en zone bâtie, contre 49 % de la zone.

**« Pourquoi avoir changé la normalisation ? »** Le min-max saturait l'indice (60 % des pixels au-dessus de 0,7). Le rang donne une échelle lisible, au prix de ne garder que l'ordre.

**« Que feriez-vous avec plus de temps ou de données ? »** Localiser tous les quartiers cités, obtenir des emprises d'inondation en ville (enquêtes, relevés), calibrer les seuils radar, ajouter les canaux de drainage, puis seulement envisager un modèle supervisé.

## 10. Reproduire les résultats

Depuis la racine du projet, environnement `.venv` activé :

```bash
python -m src.data.download_dem
python -m src.features.terrain
python -m src.data.download_water
python -m src.features.water_distance
python -m src.features.hydrology
python -m src.data.download_worldcover
python -m src.features.urban_mask
python -m src.data.download_sentinel1_dea
python -m src.features.flood_labels
python -m src.features.susceptibility
python -m src.models.validate_s1
python -m src.models.validation          # quartiers de référence
python -m src.models.train               # expérience d'apprentissage automatique
python -m src.visualization.mapping      # carte interactive
```

Résultats principaux : `outputs/figures/`, `outputs/validation_s1.csv`, `outputs/validation_results.csv`, `outputs/maps/susceptibility_bamako.html`.
