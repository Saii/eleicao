"""Mapa choropleth do Acre via Folium."""
from __future__ import annotations

import folium
import pandas as pd
from streamlit_folium import st_folium

from dashboard.api_client import get


def mapa_choropleth(votos_por_mun: list[dict], titulo: str = "Votos por município") -> None:
    geojson = get("/mapa/municipios.geojson")
    df = pd.DataFrame(votos_por_mun)
    if df.empty:
        df = pd.DataFrame(columns=["cod_ibge", "votos"])

    m = folium.Map(location=[-9.0, -70.0], zoom_start=6, tiles="cartodbpositron")
    folium.Choropleth(
        geo_data=geojson,
        data=df,
        columns=["cod_ibge", "votos"],
        key_on="feature.properties.cod_ibge",
        fill_color="YlOrRd",
        fill_opacity=0.75,
        line_opacity=0.4,
        legend_name=titulo,
        nan_fill_color="white",
    ).add_to(m)

    folium.GeoJson(
        geojson,
        name="Municípios",
        style_function=lambda _f: {"color": "#444", "weight": 0.6, "fillOpacity": 0},
        tooltip=folium.GeoJsonTooltip(fields=["nome"], aliases=["Município:"]),
    ).add_to(m)

    st_folium(m, height=600, use_container_width=True, returned_objects=[])
