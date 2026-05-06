from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.api_client import get
from dashboard.components.theme import brand_bar, empty_state, inject_css, require_login

st.set_page_config(page_title="Buscar candidatos", page_icon="🔍", layout="wide")
inject_css()
brand_bar()
require_login()
st.title("🔍 Buscar candidato")
st.caption("Pesquise qualquer candidato registrado no banco (4.500+ pessoas).")

c1, c2, c3, c4 = st.columns(4)
q = c1.text_input("Nome", "", placeholder="Ex: Rueda")
ano = c2.selectbox("Ano", [None, 2024, 2022, 2020], index=0)
cargo = c3.text_input("Cargo", "", placeholder="Ex: Vereador")
partido = c4.text_input("Sigla partido", "", placeholder="Ex: UNIÃO")

params = {"q": q or None, "ano": ano, "cargo": cargo or None, "partido": partido or None}
params = {k: v for k, v in params.items() if v}

with st.spinner("Buscando candidatos..."):
    resultado = get("/candidatos", params=params or None)
df = pd.DataFrame(resultado)
if df.empty:
    empty_state("🔎", "Sem resultados",
                "Tente ajustar os filtros: limpe campos, troque o ano, ou use parte do nome.")
    st.stop()

st.caption(f"**{len(df)}** candidatura(s) encontrada(s)")

max_v = max(int(df["total_votos"].max()), 1)
st.dataframe(
    df[["ano", "cargo", "nome_urna", "nome", "numero", "partido_sigla", "total_votos"]],
    use_container_width=True,
    hide_index=True,
    height=480,
    column_config={
        "ano": st.column_config.NumberColumn("Ano", format="%d", width="small"),
        "cargo": st.column_config.TextColumn("Cargo", width="medium"),
        "nome_urna": st.column_config.TextColumn("Nome de urna", width="medium"),
        "nome": st.column_config.TextColumn("Nome completo", width="large"),
        "numero": st.column_config.NumberColumn("Nº", format="%d", width="small"),
        "partido_sigla": st.column_config.TextColumn("Partido", width="small"),
        "total_votos": st.column_config.ProgressColumn(
            "Votos",
            format="%d",
            min_value=0,
            max_value=max_v,
            help="Barra proporcional ao maior votado da consulta",
        ),
    },
)

with st.expander("🔍 Ver detalhe da candidatura selecionada"):
    cid = st.selectbox(
        "Candidatura",
        options=df["candidatura_id"].tolist(),
        format_func=lambda c: f"{df.set_index('candidatura_id').loc[c, 'nome_urna']} "
                              f"({df.set_index('candidatura_id').loc[c, 'ano']})",
    )
    if cid:
        with st.spinner("Carregando detalhe..."):
            detalhe = get(f"/candidatos/{cid}")
        st.json(detalhe)
