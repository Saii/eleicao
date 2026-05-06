from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import get
from dashboard.components.theme import brand_bar, inject_css, require_login

st.set_page_config(page_title="Comparador", page_icon="⚖️", layout="wide")
inject_css()
brand_bar()
require_login()
st.title("⚖️ Comparador de candidatos")
st.caption("Compare 2 ou mais candidatos lado a lado por zona eleitoral.")

ano = st.selectbox("Ano", [2024, 2022, 2020])
cargo = st.text_input("Cargo", "VEREADOR")

candidatos_disponiveis = get("/candidatos", params={"ano": ano, "cargo": cargo, "limit": 200})
mapa_opt = {f"{c['nome_urna'] or c['nome']} ({c['partido_sigla'] or '?'}) — {c['total_votos']:,}".replace(",", "."): c
            for c in candidatos_disponiveis}

selecionados_chaves = st.multiselect(
    "Escolha 2 ou mais candidatos para comparar",
    list(mapa_opt.keys()),
    default=list(mapa_opt.keys())[:3],
)

if len(selecionados_chaves) < 2:
    st.info("Selecione pelo menos dois.")
    st.stop()

linhas = []
for chave in selecionados_chaves:
    c = mapa_opt[chave]
    det = get(f"/candidatos/{c['candidatura_id']}")
    for z in det["por_zona"]:
        linhas.append({
            "candidato": det["nome_urna"] or det["nome"],
            "zona": z["zona_numero"],
            "municipio": z["municipio_nome"],
            "votos": z["votos"],
        })

df = pd.DataFrame(linhas)
fig = px.bar(
    df, x="zona", y="votos", color="candidato",
    barmode="group", facet_row=None,
    hover_data=["municipio"],
)
fig.update_layout(height=550)
st.plotly_chart(fig, use_container_width=True)

pivot = df.pivot_table(index=["municipio", "zona"], columns="candidato", values="votos", fill_value=0)
st.dataframe(pivot, use_container_width=True)
