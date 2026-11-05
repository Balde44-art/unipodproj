# `notebooks/` — guided walk-through

The notebooks **read** results already produced by the scripts and reuse functions from `src/` (they do
not duplicate the code). Run them after the pipeline, in order, with the project's `.venv` kernel. They find
the project root whether launched from `notebooks/` or from the root.

| Notebook | Content |
|---|---|
| `01_exploration.ipynb` | Check that files exist; look at elevation, slope, waterways, height above the Niger, TWI, built-up areas, and radar images (dry vs wet). Shows why the data are skewed. |
| `02_preprocessing.ipynb` | Criteria, rank vs min-max normalisation, correlations, weight sensitivity, fluvial/local components, and how radar labels are built. |
| `03_model_training.ipynb` | Reads the check results: index vs radar water, six neighbourhoods, machine-learning test, and a summary table (question, answer, level of proof). |

File names are historical (from the first plan); the content is described above. To recompute a heavy step
from a notebook, uncomment the line provided (for example `train.run()` in notebook 03).
