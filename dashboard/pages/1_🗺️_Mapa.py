from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.api_client import get
from dashboard.components.mapa_ac import mapa_choropleth
from dashboard.components.theme import brand_bar, inject_css, require_login

st.set_page_config(page_title="Mapa do AC", page_icon="🗺️", layout="wide")
inject_css()
brand_bar()
require_login()
st.title("🗺️ Mapa do Acre")
st.caption("Distribuição de votos por município, com filtros de ano, cargo e partido.")

col1, col2, col3 = st.columns(3)
ano = col1.selectbox("Ano", [2024, 2022, 2020], index=0)

cargos = ["(todos)"] + get("/candidatos/cargos", params={"ano": ano})
cargo = col2.selectbox("Cargo", cargos, index=0)

partidos = [""] + [p["sigla"] for p in get("/partidos")]
partido = col3.selectbox("Partido (opcional)", partidos, index=0)

params: dict = {"ano": ano}
if cargo and cargo != "(todos)":
    params["cargo"] = cargo
if partido:
    params["sigla_partido"] = partido

with st.spinner("Carregando dados do mapa..."):
    dados = get("/mapa/votos-municipio", params=params)

titulo_cargo = cargo if cargo and cargo != "(todos)" else "todos os cargos"
mapa_choropleth(dados, titulo=f"Votos {titulo_cargo} — {ano}")

with st.expander("Tabela detalhada"):
    df_map = pd.DataFrame(dados)
    if not df_map.empty:
        max_v_map = max(int(df_map["votos"].max()), 1)
        st.dataframe(
            df_map[["municipio", "votos"]],
            use_container_width=True, hide_index=True, height=420,
            column_config={
                "municipio": st.column_config.TextColumn("Município"),
                "votos": st.column_config.ProgressColumn(
                    "Votos", format="%d", min_value=0, max_value=max_v_map,
                ),
            },
        )
