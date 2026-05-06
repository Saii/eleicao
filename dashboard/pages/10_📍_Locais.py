from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from dashboard.api_client import get
from dashboard.components.theme import brand_bar, empty_state, inject_css, require_login

st.set_page_config(page_title="Locais de votação", page_icon="📍", layout="wide")
inject_css()
brand_bar()
require_login()
st.title("📍 Locais de votação")
st.caption("670 escolas/prédios mapeados em 2024 com endereço e coordenadas.")

municipios = get("/mapa/municipios.geojson")
mun_opts = {f["properties"]["nome"]: f["properties"]["cod_ibge"] for f in municipios["features"]}
mun_label = st.selectbox("Município", sorted(mun_opts.keys()), index=sorted(mun_opts.keys()).index("Rio Branco"))
mun_cod = mun_opts[mun_label]

resumo = get(f"/locais-votacao/_resumo/{mun_cod}")
c1, c2, c3 = st.columns(3)
c1.metric("Locais", resumo["total"], help="Total de locais de votação no município")
c2.metric("Com coordenadas", resumo["com_coords"],
          help="Locais com latitude/longitude válidas (aparecem no mapa)")
c3.metric("Sem coordenadas", resumo["sem_coords"],
          help="Locais sem geocoding — listados abaixo do mapa com link para Google Maps")

with st.spinner(f"Carregando locais de {mun_label}..."):
    locais = get("/locais-votacao", params={"municipio_cod": mun_cod})
if not locais:
    empty_state("📍", "Sem locais cadastrados",
                f"Não há locais de votação para {mun_label} no banco. "
                "Execute `etl.tse_locais` + `etl.load_locais` para popular.")
    st.stop()

df = pd.DataFrame(locais)
com_coords = df.dropna(subset=["latitude", "longitude"]).copy()
sem_coords = df[df["latitude"].isna()].copy()

if not com_coords.empty:
    com_coords["lat"] = com_coords["latitude"].astype(float)
    com_coords["lon"] = com_coords["longitude"].astype(float)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=com_coords,
        get_position=["lon", "lat"],
        get_radius=80,
        get_fill_color=[200, 30, 0, 160],
        pickable=True,
        opacity=0.8,
    )
    view_state = pdk.ViewState(
        latitude=com_coords["lat"].mean(),
        longitude=com_coords["lon"].mean(),
        zoom=11,
        pitch=0,
    )
    tooltip = {
        "html": "<b>{nome}</b><br/>{endereco}<br/>{bairro}<br/>Zona {zona_numero} · Local {nr_local}",
        "style": {"backgroundColor": "white", "color": "black"},
    }
    deck = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip,
                    map_style="mapbox://styles/mapbox/light-v10")
    st.pydeck_chart(deck, use_container_width=True)

st.subheader(f"Lista — {mun_label}")
df_show = df[["nr_local", "zona_numero", "nome", "endereco", "bairro"]].rename(columns={
    "nr_local": "Nº local",
    "zona_numero": "Zona",
    "nome": "Nome",
    "endereco": "Endereço",
    "bairro": "Bairro",
})
st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)

if not sem_coords.empty:
    st.subheader("Locais sem georreferência")
    st.caption("Endereços disponíveis, mas sem lat/long. Use o link para localizar manualmente.")
    sem = sem_coords.copy()
    sem["mapa"] = sem.apply(
        lambda r: f"https://www.google.com/maps/search/{(str(r['endereco'] or '') + ' ' + str(r['bairro'] or '') + ' ' + mun_label).replace(' ', '+')}",
        axis=1,
    )
    st.dataframe(
        sem[["nr_local", "zona_numero", "nome", "endereco", "bairro", "mapa"]].rename(columns={
            "nr_local": "Nº", "zona_numero": "Zona", "nome": "Nome",
            "endereco": "Endereço", "bairro": "Bairro", "mapa": "Mapa",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={"Mapa": st.column_config.LinkColumn("Mapa", display_text="🔗 abrir")},
    )
