# `src/models/` — checks and the machine-learning experiment

None of these scripts changes the index. They measure how it compares with observations and whether a
trained model does better. Run after the index exists (`python -m src.features.susceptibility`).

| Script | Question | Reads | Writes |
|---|---|---|---|
| `validate_s1.py` | Do pixels where radar saw new water in 2024 score higher on the index? | index + components, `flood_s1_count_utm.tif`, `permanent_dark_utm.tif`, criteria rasters, urban mask | `outputs/validation_s1.csv`, `outputs/figures/validation_s1.png` |
| `validation.py` | Where do the documented flooded neighbourhoods fall on the index? | the rasters above, `data/reference/flood_reference_points.csv` | `outputs/validation_results.csv` |
| `train.py` | Does a trained model beat simple references on the radar labels? | criteria rasters, labels, built fraction | `outputs/model_s1_results.csv`, `outputs/figures/model_s1.png` |

## `validate_s1.py`

Positives = pixels flooded on ≥ 2 of 5 dates. Negatives = never detected and not dark all year. It reports
**AUC** and the share of positives in the top 10/20/30% of scores, for four strata: whole area,
"low plain" (height above the Niger ≤ 15 m, the strictest), built-up only, non-built-up. It also scores
each criterion alone. Key reading: height alone gives AUC ≈ 1.00, which is **circular** (flooded pixels are
by construction just above the river), so look at the low-plain numbers.

## `validation.py`

For each neighbourhood in the CSV with coordinates: mean score in a disc (500–600 m), its **percentile
among built-up pixels**, and the percentile of each criterion. It prints an AUC only when there are at
least 2 flooded **and** 2 non-flooded places. There are no documented non-flooded places yet, so no AUC.
To add a place: fill `lat`, `lon` (click on `outputs/maps/pick_points.html`) in the CSV and rerun.

## `train.py`

Gradient boosting and logistic regression predicting radar water, with **spatial block cross-validation**
(3 km blocks, `BLOCK_PX = 100`, 5 folds): a whole block is either in training or in test, so the model
cannot copy its neighbours. Compared with four no-learning references (height, distance, fluvial
component, combined index) and several feature sets (all four criteria, without height, slope + TWI only,
plus built fraction). No coordinates are used as features. Main finding: no decisive gain over height alone.
Hyperparameters are fixed, not searched. Takes a few minutes.

## Legacy file: `validate_index.py`

An earlier validation based on `data/external/flood_reference_sites.csv` (geocoded with
`src/data/geocode_sites.py`). It is **superseded by `validation.py`** and writes to the **same**
`outputs/validation_results.csv`. Do not run it unless you mean to overwrite that file; it can be deleted.

## Reading AUC

0.5 = chance, 1.0 = perfect separation. With neighbouring pixels so similar, AUC is descriptive, not a
significance test. These labels are sensor-derived, not ground truth.
