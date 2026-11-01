"""Tableau de bord Streamlit de GeoAI Mali (v0.1 : indice de susceptibilité multicritère).

Lancement depuis la racine du projet :
    streamlit run app/dashboard.py
"""

import sys
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.visualization.mapping import SCORE_TIF, base_map, build_susceptibility_map  # noqa: E402

st.set_page_config(page_title="GeoAI Mali", layout="wide")
st.title("GeoAI Mali")
st.caption("Geospatial Artificial Intelligence for Environmental Risk Analysis — prototype expérimental v0.1")

st.warning(
    "Indice relatif de susceptibilité (hauteur au-dessus du Niger, distance aux cours d'eau, pente). "
    "Ce n'est pas une prédiction d'inondation : poids choisis par expert, pas encore validés "
    "sur des inondations observées."
)


@st.cache_resource
def load_map():
    return build_susceptibility_map()


if SCORE_TIF.exists():
    st_folium(load_map(), width=None, height=650, returned_objects=[])
else:
    st.info("Indice non encore calculé : lance d'abord `python -m src.features.susceptibility`.")
    st_folium(base_map(), width=None, height=550, returned_objects=[])
