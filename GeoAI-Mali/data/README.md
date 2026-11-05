# `data/` — what lives where

| Folder | Content | In Git? |
|---|---|---|
| `raw/` | Downloads as received: DEM, OSM waterways, WorldCover, Sentinel-1 (`raw/s1/`) | No (except `osm_water_bamako.geojson`, needed by the dashboard) |
| `processed/` | Rasters on the common 30 m UTM grid: terrain, water, TWI, urban mask, radar labels, index | No (except `susceptibility_*.tif` and `flood_s1_count_utm.tif`, needed by the dashboard) |
| `external/` | Legacy: `flood_reference_sites.csv` from the first, geocoding-based approach | No |
| `reference/` | **Hand-collected reference neighbourhoods** (`flood_reference_points.csv`) | **Yes** |

`DATA_SOURCES.md` lists every source with licence, resolution, known limits and open points.

## `reference/flood_reference_points.csv`

One row per place. Columns: `name`, `commune`, `flooded` (1 = documented as flooded, 0 = known dry),
`lat`, `lon` (clicked on satellite imagery), `radius_m` (500–600 m, covers the uncertainty of a point in a
1–2 km neighbourhood), `date`, `certainty`, `source`, `notes`. All six places so far are flooded places
cited in articles, press or a thesis; **no place is documented as dry**, so an AUC cannot be computed yet.
Add rows only with a written source.

## Rebuilding `raw/` and `processed/`

Run the pipeline in `src/README.md`; the files are fully reproducible from public sources.
