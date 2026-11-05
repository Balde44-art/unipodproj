# GeoAI Mali

**Geospatial Artificial Intelligence for Environmental Risk Analysis**

## Overview

GeoAI Mali is an experimental project exploring the application of Artificial Intelligence and geospatial data to environmental risk analysis in Mali.

## Initial Research Direction

The first use case focuses on exploring flood susceptibility mapping around Bamako using geospatial and environmental data.

## Objectives

- Explore geospatial datasets.
- Process and analyze environmental information.
- Develop machine learning experiments.
- Visualize geospatial analysis results.
- Evaluate the potential of AI for environmental risk assessment.

## Current Status

Prototype v0.3: a **relative flood-susceptibility index** (0 to 1, 30 m resolution) around Bamako, built from terrain and hydrology, with a Sentinel-1 consistency check and a six-neighbourhood case check.

**This is not a flood prediction.** Weights are expert choices (tested for sensitivity, never tuned on observations). A machine-learning experiment (gradient boosting and logistic regression, spatial block cross-validation) was run on the Sentinel-1 labels: it gives no decisive gain over height above the Niger alone (AUC 0.96 vs 0.95 within 15 m of river level), because the only large-scale labels available show river water, not urban flooding. It is reported as a result, not retained as the main product. Details and honest limits: [`docs/METHODOLOGIE.md`](docs/METHODOLOGIE.md) (in French).

| Component | What it uses | Check |
|---|---|---|
| Fluvial | height above the Niger, distance to waterways | Consistent with Sentinel-1 water 2024 (AUC 0.98; 0.84 within 15 m of river level). Partly circular. |
| Local | slope, topographic wetness index (TWI) | **Not validated** (no urban flood labels). Weak against river labels. |
| Combined index | all four criteria, equal weights | 4 of 6 cited flooded neighbourhoods rank above the 70th percentile of built-up areas; 2 rank below the median |

## Technologies

- Python 3.11
- NumPy, pandas
- GeoPandas, Rasterio
- scikit-learn
- Folium
- Streamlit

## Project structure

```
GeoAI-Mali/
├── data/            # raw / processed / external (not versioned)
├── notebooks/       # exploration and experiments
├── src/             # reusable code (data, features, models, visualization)
├── app/             # Streamlit dashboard
├── outputs/         # figures and maps
├── requirements.txt
└── README.md
```

## Getting started

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -c "import numpy, pandas, sklearn, geopandas, folium, streamlit; print('GeoAI Mali - Environment OK')"
```

Windows (PowerShell): `py -3.11 -m venv .venv` then `.\.venv\Scripts\Activate.ps1`, then the same `pip` commands.

## Research Principle

All experimental results are documented, limits are stated next to results, and synthetic data would be clearly distinguished from real-world observations (none is used in the results presented here).

## Data sources

Full catalogue with licences, resolutions and known limits: [`data/DATA_SOURCES.md`](data/DATA_SOURCES.md).

| Dataset | Role | Status |
|---------|------|--------|
| Copernicus DEM GLO-30 | Elevation, slope, hydrology (TWI) | **Used** |
| OpenStreetMap (Overpass) | Waterways, Niger reference | **Used** |
| ESA WorldCover 2021 | Built-up mask (comparison only) | **Used** |
| Sentinel-1 RTC (Digital Earth Africa `s1_rtc`) | Water labels, 2024 rainy season (consistency check) | **Used** |
| Reference neighbourhoods (articles, press, thesis) | Case check, 6 locations | **Used** (`data/reference/flood_reference_points.csv`) |
| HydroSHEDS, CHIRPS, Sentinel-2 | Not needed so far | Identified, not used |
| Urban flood labels | Target variable | **Open problem**: no open urban flood extent found for Bamako |
web_site summarize : https://unipodproj-aqsfenyhpmmaej4lyhfdpx.streamlit.app/ 
## Run the pipeline

From the project root with the virtual environment active (see `docs/METHODOLOGIE.md`, section 10, for the full list):

```bash
python -m src.data.download_dem && python -m src.features.terrain
python -m src.data.download_water && python -m src.features.water_distance
python -m src.features.hydrology
python -m src.data.download_worldcover && python -m src.features.urban_mask
python -m src.data.download_sentinel1_dea && python -m src.features.flood_labels
python -m src.features.susceptibility
python -m src.models.validate_s1 && python -m src.models.validation
python -m src.models.train                 # ML experiment, outputs/model_s1_results.csv
python -m src.visualization.mapping        # outputs/maps/susceptibility_bamako.html
streamlit run app/dashboard.py
```
