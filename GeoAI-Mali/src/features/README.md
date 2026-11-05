# `src/features/` — from raw data to rasters, index and labels

Each script reads rasters/vectors, computes one thing, and writes a GeoTIFF in `data/processed/` (plus a
check figure in `outputs/figures/`). All outputs share the same 30 m UTM grid.

## Terrain and water

| Script | Needs | Writes | What it computes |
|---|---|---|---|
| `terrain.py` | `raw/dem_bamako_cop30.tif` | `dem_bamako_utm.tif`, `slope_bamako_utm.tif` | Reprojects the DEM to UTM 29N, 30 m (bilinear), then slope in degrees from `np.gradient`. Slope needs metres in x, y *and* z, hence the reprojection first. |
| `water_distance.py` | DEM (UTM), `raw/osm_water_bamako.geojson` | `dist_water_bamako_utm.tif`, `height_above_niger_utm.tif` | Distance (m) to the nearest OSM waterway, and **height above the Niger** (altitude minus the river surface, taken as a 5-pixel minimum filter along the Niger). Only the Niger is used as reference: using every small stream produced artificial facets. The Niger is found by a name containing "niger". |
| `hydrology.py` | DEM (UTM) | `flow_accumulation_utm.tif`, `twi_utm.tif` | Pure NumPy: depression filling (Priority-Flood + epsilon), D8 flow directions, flow accumulation, then **TWI** = ln(a / tan β) with a slope floor of 0.5°. TWI is high where water converges. Noisy in towns because the DEM includes buildings. |
| `urban_mask.py` | WorldCover, DEM | `built_fraction_utm.tif`, `urban_mask_utm.tif` | Built-up fraction per 30 m pixel; mask = fraction above 25%, dilated by 3 pixels. Used to compare urban vs non-urban results, **not** as an index criterion. |

## The index

`susceptibility.py` (v0.3) — the core of the project.

- **Criteria**: `height`, `distance`, `slope` (low = exposed) and `twi` (high = exposed).
- **Rank normalisation** (`normalize_low_is_risky`, `normalize_high_is_risky`): each criterion becomes a
  percentile in [0, 1]. Min-max was tried first and saturated (60% of pixels above 0.7).
- **Scenarios** (`SCENARIOS`): equal weights (main) plus four others. **Robustness**
  (`robustness`): 100 random weight sets, share of draws where a pixel is in the top 20%.
- **Components** (`COMPONENTS`): `fluviale` = height + distance, `locale` = slope + TWI.
- **Writes**: `susceptibility_bamako_utm.tif` (combined), `susceptibility_robust_utm.tif`,
  `susceptibility_fluvial_utm.tif`, `susceptibility_local_utm.tif`, and a 4-panel figure.
- **To change the weights**: edit `SCENARIOS` / `MAIN_SCENARIO`. Do not tune them to improve an AUC: the
  radar labels only describe river water, so that would be circular (see `docs/METHODOLOGIE.md`, §6).
- The index is **relative** (a rank), not a flood probability.

## Radar flood labels

`flood_labels.py` — builds "new water" maps from Sentinel-1.

1. Convert to dB, 3×3 mean filter on linear intensity (reduces speckle).
2. Dry reference = median of the 3 March–April images.
3. A pixel is flooded on a date if: darker than `T_WATER` (−18 dB), dropped by more than `|T_CHANGE|`
   (3 dB) vs the reference, **not** already dark in the dry season, and part of a group of at least
   `MIN_PIXELS` (8) connected pixels.
4. Resample to the common grid (flooded share ≥ `MIN_FRACTION` = 0.3), drop slopes above `MAX_SLOPE_DEG`
   (8°), and count on how many of the 5 dates each pixel is flooded.
- **Writes**: `flood_s1_count_utm.tif` (0–5, −1 = no data), `permanent_dark_utm.tif` (dark all year:
  river, shadows; excluded from checks), `outputs/figures/flood_labels_bamako.png`.
- **Thresholds are common literature values, not calibrated on Bamako.** Change them at the top of the file.
- **Limit**: the result is mostly the Niger's rise and floodplain; only ~6% of detected pixels are in
  built-up areas. A pixel at 0 means "not detected", not "never flooded".

## Placeholder

`engineering.py` is an empty stub from the first setup (not used).
