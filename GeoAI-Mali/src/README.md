# `src/` — code map

All code is run **from the project root** as a module (`python -m src.<package>.<script>`), never by
double-clicking or `cd`-ing into a subfolder. Docstrings and comments in the scripts are in French;
each script starts with a docstring that explains *why* it exists, its inputs/outputs and its limits.

```
src/
├── data/            download raw data (DEM, rivers, land cover, radar) and prepare reference points
├── features/        turn raw data into rasters: terrain, water, hydrology, urban mask, index, radar labels
├── models/          checks of the index against observations, and the machine-learning experiment
└── visualization/   interactive maps (Folium)
```

There is no `src/terrain/` folder: terrain code (elevation, slope) is `src/features/terrain.py`.

## Pipeline, in order

Each step reads files made by the steps above it. If a script says *file not found*, run the step that
produces that file first.

| # | Command | Produces (in `data/` unless noted) |
|---|---|---|
| 1 | `python -m src.data.download_dem` | `raw/dem_bamako_cop30.tif` |
| 2 | `python -m src.features.terrain` | `processed/dem_bamako_utm.tif`, `slope_bamako_utm.tif` |
| 3 | `python -m src.data.download_water` | `raw/osm_water_bamako.geojson` |
| 4 | `python -m src.features.water_distance` | `processed/dist_water_bamako_utm.tif`, `height_above_niger_utm.tif` |
| 5 | `python -m src.features.hydrology` | `processed/flow_accumulation_utm.tif`, `twi_utm.tif` |
| 6 | `python -m src.data.download_worldcover` | `raw/worldcover_bamako_2021.tif` |
| 7 | `python -m src.features.urban_mask` | `processed/built_fraction_utm.tif`, `urban_mask_utm.tif` |
| 8 | `python -m src.data.download_sentinel1_dea` | `raw/s1/{vv,vh,mask}_YYYYMMDD.tif` |
| 9 | `python -m src.features.flood_labels` | `processed/flood_s1_count_utm.tif`, `permanent_dark_utm.tif` |
| 10 | `python -m src.features.susceptibility` | `processed/susceptibility_{bamako,robust,fluvial,local}_utm.tif` |
| 11 | `python -m src.models.validate_s1` | `outputs/validation_s1.csv`, figure |
| 12 | `python -m src.models.validation` | `outputs/validation_results.csv` |
| 13 | `python -m src.models.train` | `outputs/model_s1_results.csv`, figure |
| 14 | `python -m src.visualization.mapping` | `outputs/maps/susceptibility_bamako.html` |

Steps 2 to 9 can be partly reordered as long as their inputs exist. Step 10 needs 2, 4 and 5.
Steps 11 to 13 need 9 and 10.

## Conventions shared by all scripts

- **Study area**: `BBOX = (-8.15, 12.50, -7.85, 12.80)` (west, south, east, north), defined once in
  `src/data/download_dem.py` and imported by the other download scripts.
- **One grid**: every raster in `data/processed/` is on the same grid as `dem_bamako_utm.tif`
  (UTM zone 29N, EPSG:32629, 30 m pixels). That is why they can be stacked pixel by pixel.
- **File names**: `*_utm.tif` means "on the common 30 m UTM grid".
- **Generated files are not committed** (`data/raw`, `data/processed`, `outputs` are in `.gitignore`),
  except the few results the deployed dashboard needs (see `data/README.md`).
- **Unused stubs**: `src/data/preprocessing.py` and `src/features/engineering.py` are empty placeholders
  from the first setup. Their work is done by the scripts listed above.

See also: `docs/METHODOLOGIE.md` (why each choice was made, with results and limits).
