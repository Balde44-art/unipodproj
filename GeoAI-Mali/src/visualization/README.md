# `src/visualization/` — maps

## `mapping.py` → the interactive map

`python -m src.visualization.mapping` writes `outputs/maps/susceptibility_bamako.html` (open it in a
browser). Layers:

| Layer | File used | Shown by default |
|---|---|---|
| Combined index (0–1) | `susceptibility_bamako_utm.tif` | yes |
| Fluvial component | `susceptibility_fluvial_utm.tif` | no |
| Local component (not validated) | `susceptibility_local_utm.tif` | no |
| Robustness to weights | `susceptibility_robust_utm.tif` | no |
| Radar-detected water 2024 | `flood_s1_count_utm.tif` | no |
| Waterways (OpenStreetMap) | `raw/osm_water_bamako.geojson` | yes |
| Reference neighbourhoods (red) | `reference/flood_reference_points.csv` | yes |

A fixed text box states that this is a relative index, not a prediction, and which part is validated.
Optional layers are skipped silently if their file is missing. Useful functions:
`raster_to_overlay(tif, cmap, vmin, vmax, mask_below)` (reprojects a raster to EPSG:4326 and colours it),
`build_susceptibility_map()`, and `base_map()` (used by the dashboard). **To add a layer**, add a line to
`optional_layers` in `build_susceptibility_map`.

## `pick_points.py` → finding coordinates

`python -m src.visualization.pick_points` writes `outputs/maps/pick_points.html`: a satellite basemap
(Esri) with a place search box. **Click on a place and a bubble shows its latitude and longitude**; copy
them into `data/reference/flood_reference_points.csv` (`flooded = 1` if the source documents flooding,
`0` for a place known to be dry). Red dots = flooded, green = not flooded, blue = proposals from
`src/data/locate_places.py`.
Note: the search box code is duplicated in the script (two `Geocoder` lines); harmless, can be cleaned.
