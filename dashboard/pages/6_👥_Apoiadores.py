from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.api_client import autenticado, get, post
from dashboard.components.theme import brand_bar, empty_state, inject_css

st.set_page_config(page_title="Apoiadores", page_icon="👥", layout="wide")
inject_css()
brand_bar()
st.title("👥 Apoiadores")
st.caption("Cadastro segmentado por município, zona e bairro.")

if not autenticado():
    st.warning("Faça login na página inicial para acessar a gestão.")
    st.stop()

tab_lista, tab_novo = st.tabs(["Lista", "Novo apoiador"])

# Carrega lista de municípios uma vez (resolve cod_ibge ↔ nome)
muni_geo = get("/mapa/municipios.geojson")
muni_options = sorted(
    [(f["properties"]["cod_ibge"], f["properties"]["nome"]) for f in muni_geo["features"]],
    key=lambda x: x[1],
)
nome_por_cod = {cod: nome for cod, nome in muni_options}
cod_por_nome = {nome: cod for cod, nome in muni_options}
nomes_municipios = ["(não informado)"] + [n for _, n in muni_options]


with tab_lista:
    with st.spinner("Carregando apoiadores..."):
        apoiadores = get("/campanha/apoiadores")
    if apoiadores:
        df = pd.DataFrame(apoiadores)
        # Substitui código IBGE pelo nome do município na exibição
        df["municipio"] = df["municipio_cod"].map(nome_por_cod).fillna("—")
        # Reordena colunas — esconde municipio_cod
        cols_show = [c for c in df.columns if c != "municipio_cod"]
        # Coloca "municipio" logo após nome
        if "municipio" in cols_show:
            cols_show.remove("municipio")
            if "nome" in cols_show:
                idx = cols_show.index("nome") + 1
                cols_show.insert(idx, "municipio")
            else:
                cols_show.insert(0, "municipio")
        st.caption(f"**{len(df)}** apoiador(es) cadastrado(s)")
        st.dataframe(
            df[cols_show], use_container_width=True, hide_index=True, height=480,
            column_config={
                "municipio": st.column_config.TextColumn("Município"),
                "nivel_engajamento": st.column_config.NumberColumn(
                    "Engajamento", format="⭐ %d",
                    help="1=lead · 2=apoiador · 3=militante · 4=liderança",
                ),
            },
        )
    else:
        empty_state("👥", "Nenhum apoiador cadastrado ainda",
                    "Use a aba 'Novo apoiador' acima para cadastrar o primeiro contato da campanha.")

with tab_novo:
    with st.form("novo_apoiador"):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome*")
        telefone = c2.text_input("Telefone")
        email = c1.text_input("E-mail")
        cpf = c2.text_input("CPF")
        municipio_nome = c1.selectbox(
            "Município", nomes_municipios, index=0,
            help="Lista oficial dos 22 municípios do Acre",
        )
        zona = c2.number_input("Zona eleitoral", min_value=0, step=1)
        bairro = st.text_input("Bairro")
        nivel = st.slider("Nível de engajamento", 1, 4, 1,
                          help="1=lead, 2=apoiador, 3=militante, 4=liderança")
        obs = st.text_area("Observações")
        if st.form_submit_button("Cadastrar", type="primary"):
            if not nome:
                st.error("Nome é obrigatório.")
            else:
                muni_cod = cod_por_nome.get(municipio_nome)  # None se "(não informado)"
                post("/campanha/apoiadores", {
                    "nome": nome, "telefone": telefone or None, "email": email or None,
                    "cpf": cpf or None,
                    "municipio_cod": muni_cod,
                    "zona_numero": int(zona) or None, "bairro": bairro or None,
                    "nivel_engajamento": nivel, "observacoes": obs or None,
                })
                st.success(f"✅ {nome} cadastrado em {municipio_nome}!")
                st.cache_data.clear()
