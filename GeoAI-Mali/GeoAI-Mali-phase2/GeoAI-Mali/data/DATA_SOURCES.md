# Catalogue des sources de données — GeoAI Mali (phase 2)

Dernière mise à jour : 2026-10-31. Les informations ci-dessous viennent des pages de documentation citées.
Les points marqués **[à vérifier]** n'ont pas pu être confirmés et doivent être contrôlés avant utilisation dans le mémoire ou devant le jury.

## 1. Données explicatives (les facteurs)

| Donnée | Rôle pour les inondations | Résolution | Licence | Accès |
|---|---|---|---|---|
| **Copernicus DEM GLO-30** | Altitude, pente, zones basses | ~30 m | Gratuite (GLO-30 public) | AWS S3 `copernicus-dem-30m` ; copie Digital Earth Africa |
| **HydroSHEDS v1.1** | Direction et accumulation d'écoulement, réseau hydrographique | 3 à 30 arc-secondes | Conditions d'utilisation HydroSHEDS **[à vérifier]** | hydrosheds.org/downloads (GeoTIFF) |
| **CHIRPS** | Pluie quotidienne | 0,05° (~5 km), 1981 à aujourd'hui | Domaine public | AWS S3 `deafrica-input-datasets` ; Sandbox Digital Earth Africa |
| **ESA WorldCover** | Occupation du sol (bâti, végétation, eau, sol nu) | ~10 m, années 2020 et 2021 | CC BY 4.0 | AWS S3 `esa-worldcover` ; Sandbox Digital Earth Africa |
| **OpenStreetMap (Geofabrik, Mali)** | Routes, bâtiments, cours d'eau | Vectoriel | ODbL **[à vérifier]** | download.geofabrik.de/africa/mali.html |
| **Sentinel-2 L2A** | Images optiques, indices (NDVI, NDWI) | 10 à 60 m selon les bandes | Libre et gratuit **[à vérifier : conditions précises]** | Copernicus Data Space Ecosystem |

Notes importantes :
- Copernicus DEM : précision verticale globale annoncée par validation ICESat : RMSE de 1,68 m. Sur du terrain urbain très plat, 1,68 m est une erreur importante par rapport aux écarts d'altitude entre quartiers. À discuter dans les limites.
- CHIRPS : 5 km est grossier. Sur une ville comme Bamako, la pluie sera quasi identique pour beaucoup de points. La pluie sera utile pour la dimension temporelle, pas pour distinguer des quartiers.
- CHIRPS : les estimations satellitaires peuvent sous-estimer les pluies extrêmes.
- ESA WorldCover : précision globale 2021 d'environ 76,5 % en Afrique (2020 : 73,6 %). Ce n'est pas une vérité terrain.
- La page Digital Earth Africa du DEM mentionne une incohérence sur les conventions de nom des fichiers : vérifier les valeurs réelles dans le bucket.

## 2. Données de référence (la variable à prédire) — le point critique

C'est la partie la plus difficile. Sans exemples fiables de « zone inondée / zone non inondée », aucun modèle supervisé n'est défendable.

| Source | Ce qu'elle apporte | Limites |
|---|---|---|
| **Global Flood Database (Tellman et al., Nature 2021)** | Étendues d'inondation 2000–2018, issues de MODIS, 913 événements validés dans le monde | Résolution annoncée à 250 m (la page est incohérente et mentionne aussi 30 m : **[à vérifier]**). Trop grossier pour des quartiers de Bamako. Licence CC BY-NC 4.0 (usage non commercial). Couverture de Bamako **[à vérifier]**. |
| **Dartmouth Flood Observatory (archive)** | Rapports d'événements et emprises approximatives, avec dates et bilans | Données surtout à l'échelle de l'événement, pas du pixel |
| **JRC Global Surface Water** | Eau permanente et saisonnière depuis 1984, utile pour séparer eau permanente et crue | Ce n'est pas un inventaire d'inondations urbaines |
| **Rapports officiels et presse (2024)** | Bilan du Comité interministériel au 5 septembre 2024 : 57 décès, 126 034 sinistrés, 9 331 effondrements de maisons | Bilan national, **aucun quartier de Bamako cité** dans l'article consulté. Inutilisable tel quel comme étiquette spatiale. |
| **Cartes dérivées de Sentinel-1 / Sentinel-2** | Possibilité de cartographier nous-mêmes l'eau pendant un événement connu | À construire : demande du travail et une validation, la couverture nuageuse gêne l'optique |

Conclusion provisoire : il n'existe pas, dans ce que nous avons trouvé, de jeu prêt à l'emploi d'inondations urbaines étiquetées à l'échelle des quartiers de Bamako. Il faudra soit construire nos étiquettes à partir d'images satellites sur des événements datés, soit reformuler l'objectif (voir README).

## 3. Sources consultées

- Copernicus DEM (Digital Earth Africa) : https://docs.digitalearthafrica.org/en/latest/data_specs/COP_DEM_specs.html
- Global Flood Database (Google Earth Engine) : https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1
- CHIRPS (Digital Earth Africa) : https://docs.digitalearthafrica.org/en/latest/data_specs/CHIRPS_specs.html
- ESA WorldCover (Digital Earth Africa) : https://docs.digitalearthafrica.org/en/latest/data_specs/ESA_WorldCover_specs.html
- HydroSHEDS : https://hydrosheds.org/downloads
- Geofabrik : https://download.geofabrik.de
- JRC Global Surface Water Explorer : https://data.jrc.ec.europa.eu/dataset/jrc-gswe-global-surface-water-explorer-v1
- Dartmouth Flood Observatory : https://floodobservatory.colorado.edu
- Bilan des inondations 2024 (allAfrica) : https://fr.allafrica.com/stories/202409080084.html
- Copernicus Data Space Ecosystem : https://dataspace.copernicus.eu
