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

Research and development — initial setup and technical exploration.

**No operational flood prediction model has been developed yet.**

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

## Getting started (Windows, PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -c "import numpy, pandas, sklearn, geopandas, folium, streamlit; print('GeoAI Mali - Environment OK')"
```

## Research Principle

All experimental results will be documented, and synthetic data will be clearly distinguished from real-world observations.

## Data sources (to document as we go)

| Dataset | Source | Date accessed | Notes |
|---------|--------|---------------|-------|
| _à compléter_ | | | |
