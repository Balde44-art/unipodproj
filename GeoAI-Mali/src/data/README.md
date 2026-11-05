# `src/data/` — getting the data

Scripts that **download** raw data into `data/raw/`, plus helpers for the reference neighbourhoods.
They only need an internet connection (no account), and read just the window around Bamako rather than
whole files. Run from the project root: `python -m src.data.<script>`.

## Download scripts

| Script | Source | Output | Notes |
|---|---|---|---|
| `download_dem.py` | Copernicus DEM GLO-30 (~30 m), public AWS bucket `copernicus-dem-30m` | `data/raw/dem_bamako_cop30.tif` | Defines `BBOX`, used by other scripts. Tiles are merged with `nodata=NaN`: an earlier version filled a row with zeros, which gave a fake 0 m altitude and an 85° slope. |
| `download_water.py` | OpenStreetMap via the Overpass API | `data/raw/osm_water_bamako.geojson` | Rivers and streams as **lines** (not polygons), with `kind` and `name`. Area = bbox + 0.05° margin. Cite "© OpenStreetMap contributors" (ODbL). |
| `download_worldcover.py` | ESA WorldCover 2021 v200 (10 m), tile N12W009 | `data/raw/worldcover_bamako_2021.tif` | Class 50 = built-up. CC BY 4.0. |
| `download_sentinel1_dea.py` | Digital Earth Africa `s1_rtc` (Sentinel-1, terrain-corrected, ~20 m) | `data/raw/s1/vv_`, `vh_`, `mask_` + `YYYYMMDD.tif` | Holds `WET_DATES` (5 dates, Aug–Oct 2024) and `DRY_DATES` (3 dates, Mar–Apr 2024), same orbit 16. Values are **linear** intensity, not dB. Licence of `s1_rtc`: to verify. |

## Feasibility and helpers

| Script | What it does |
|---|---|
| `search_sentinel1.py` | Asks the Copernicus Data Space catalogue which Sentinel-1 images exist over Bamako and how much of the area each covers. Writes `outputs/s1_availability.csv`. It was the feasibility check before choosing the radar dates (the area is covered by two image "slices", 68% + 32%). |
| `locate_places.py` | For rows of `data/reference/flood_reference_points.csv` without coordinates, proposes candidate locations from OpenStreetMap names → `outputs/proposed_coordinates.csv` (shown as blue dots by `pick_points`). **Proposals only: verify on the map.** |
| `geocode_sites.py` | **Legacy.** Geocodes `data/external/flood_reference_sites.csv` with Nominatim. Superseded by clicking points on `pick_points.html`. Only needed with the legacy `validate_index.py` (see `src/models/README.md`). |
| `preprocessing.py` | Empty placeholder, not used. |

## If something fails

- *Connection or 403/404 errors*: the public buckets and APIs are sometimes slow; run the script again.
- *Sentinel-1 returns no item for a date*: the date list in `download_sentinel1_dea.py` must match images
  that exist (check with `search_sentinel1`).
- To change the study area, edit `BBOX` in `download_dem.py`, then rerun the whole pipeline.
