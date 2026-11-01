# Catalogue des sources de données — GeoAI Mali (phase 2)

Dernière mise à jour : 2026-11-01. Les informations ci-dessous viennent des pages de documentation citées.
Les points marqués **[à vérifier]** n'ont pas pu être confirmés et doivent être contrôlés avant utilisation dans le mémoire ou devant le jury.

## 0. Ce qui est réellement utilisé (état au 1er novembre 2026)

| Donnée | Version / accès | Fichier produit |
|---|---|---|
| Copernicus DEM GLO-30 | tuiles COG sur AWS, emprise -8,15 / 12,50 / -7,85 / 12,80 | `data/raw/dem_bamako_cop30.tif`, `data/processed/dem_bamako_utm.tif` |
| OpenStreetMap | API Overpass (emprise + 0,05°), 883 objets, 1042 segments, lignes | `data/raw/osm_water_bamako.geojson` |
| ESA WorldCover | 2021 v200, tuile N12W009, classe 50 (bâti) | `data/processed/built_fraction_utm.tif`, `urban_mask_utm.tif` |
| Sentinel-1 RTC | Digital Earth Africa `s1_rtc` (STAC `explorer.digitalearth.africa/stac/search`), orbite 16 ascendante, VV/VH linéaire ~20 m ; 5 dates 2024 (14 et 26 août, 7 et 19 septembre, 1er octobre) et 3 dates de référence sèche (11 et 23 mars, 4 avril) | `data/raw/s1/`, `data/processed/flood_s1_count_utm.tif` |
| Quartiers de référence | articles, presse, mémoire AFRIGIST (voir le CSV) ; coordonnées relevées à la main sur imagerie satellite | `data/reference/flood_reference_points.csv` |

Remarques propres aux données utilisées :
- **Sentinel-1** : le produit est traité par Digital Earth Africa à partir de données Copernicus Sentinel-1. Les étiquettes d'eau sont **dérivées d'un capteur** (seuils -18 dB et -3 dB, non calibrés sur Bamako) et ne montrent que l'eau fluviale et saisonnière ; le radar voit mal l'eau en ville dense. Les images de 2019 n'ont pas été retenues : la plus proche après le 16 mai 2019 est à +9 jours.
- **Quartiers de référence** : coordonnées au centre du quartier (un quartier fait 1 à 2 km), rayon de 500 à 600 m. Aucun lieu documenté comme non inondé.
- **Licences** : à contrôler avant toute diffusion hors du mémoire (OpenStreetMap : ODbL ; WorldCover : CC BY 4.0 ; Copernicus Sentinel-1 et DEM : conditions Copernicus). La licence exacte de `s1_rtc` est **[à vérifier]** sur la page Digital Earth Africa.

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
| **Cartes dérivées de Sentinel-1 (réalisé, 2024)** | Eau nouvelle par détection de changement, 5 dates de la saison des pluies | **Fait** : 16,2 km² détectés au moins une fois, 6 % seulement en zone bâtie. Montre l'eau fluviale, pas l'inondation urbaine (voir `docs/METHODOLOGIE.md`) |
| **Cartes dérivées de Sentinel-2** | Eau optique pendant un événement | Non fait : couverture nuageuse en saison des pluies |
| **Rapport GDACS « Mali floods » (9 septembre 2024)** | Contexte : 55 décès, ~74 000 personnes touchées à la date du 2 septembre (source PNRRC) | Échelle du pays, par cercle ; aucun quartier de Bamako, pas de données à télécharger. Inutilisable comme étiquette |
| **Copernicus EMS EMSR561** | — | Concerne le **Malawi** (tempête Ana, 2022) : sans rapport avec le Mali |
| **Projet OSM « Community Mapping for a Resilient Bamako »** | Cartographie communautaire (drainage, déchets, eau) | Page de présentation uniquement ; aucune donnée d'inondation ni lien de téléchargement trouvés |

Conclusion (1er novembre 2026) : il n'existe pas, dans ce que nous avons trouvé, de jeu ouvert d'inondations urbaines étiquetées à l'échelle des quartiers de Bamako. Nous avons construit des étiquettes radar (2024), qui montrent le fleuve mais pas la ville. L'objectif a donc été reformulé : un indice relatif de susceptibilité, contrôlé en partie par ces étiquettes et par six quartiers cités, sans modèle supervisé (voir `docs/METHODOLOGIE.md`, sections 6 et 7).

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
- Digital Earth Africa, Sentinel-1 RTC : https://docs.digitalearthafrica.org/en/latest/data_specs/Sentinel-1_specs.html
- GDACS, Mali floods (9 septembre 2024) : https://gdacs.org/contentdata/maps/daily/FL/1102792/ECDM_20240909_Mali_floods.pdf
- Copernicus EMS EMSR561 (Malawi) : https://emergency.copernicus.eu/mapping/list-of-components/EMSR561
- OSM, Community Mapping for a Resilient Bamako : https://wiki.openstreetmap.org/wiki/Community_Mapping_For_A_Resilient_Bamako
