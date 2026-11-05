# `app/` — Streamlit dashboard

`dashboard.py` shows the interactive map (built by `src/visualization/mapping.py`) with a warning that the
index is relative and which part is validated. Locally, from the project root:

```bash
streamlit run app/dashboard.py
```

If the index has not been computed, it shows an empty map and the command to run first.

## Deploying (Streamlit Community Cloud)

1. Put the project on GitHub (the app deploys from a repository).
2. The deployed app only displays **already computed** results; it does not recompute. These files must be
   in the repository: the four `susceptibility_*.tif`, `flood_s1_count_utm.tif`,
   `raw/osm_water_bamako.geojson` and `reference/flood_reference_points.csv`. The `.gitignore` is set up to
   let them through while keeping the heavy data out.
3. `app/requirements.txt` lists the minimal dependencies for the cloud build.
4. On share.streamlit.io: choose the repository, branch `main`, main file `app/dashboard.py`, Python 3.11.
