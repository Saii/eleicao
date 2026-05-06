from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.api_client import autenticado, get, post
from dashboard.components.theme import brand_bar, empty_state, inject_css

st.set_page_config(page_title="Anotações", page_icon="📝", layout="wide")
inject_css()
brand_bar()
st.title("📝 Anotações")
st.caption("Notas territoriais com tags por município/zona/bairro.")

if not autenticado():
    st.warning("Faça login para acessar.")
    st.stop()

tab_lista, tab_novo = st.tabs(["Lista", "Nova anotação"])

with tab_lista:
    with st.spinner("Carregando anotações..."):
        anotacoes = get("/campanha/anotacoes")
    if anotacoes:
        st.caption(f"**{len(anotacoes)}** anotação(ões)")
        st.dataframe(pd.DataFrame(anotacoes), use_container_width=True, hide_index=True, height=480)
    else:
        empty_state("📝", "Sem anotações ainda",
                    "Use a aba 'Nova anotação' para registrar observações de campanha "
                    "por município, zona ou bairro — útil para passar contexto ao time.")

with tab_novo:
    with st.form("nova_anotacao"):
        titulo = st.text_input("Título*")
        conteudo = st.text_area("Conteúdo")
        c1, c2 = st.columns(2)
        municipio_cod = c1.number_input("Cod. IBGE município", min_value=0, step=1)
        zona = c2.number_input("Zona", min_value=0, step=1)
        bairro = st.text_input("Bairro")
        tags_raw = st.text_input("Tags (separadas por vírgula)")
        if st.form_submit_button("Salvar"):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            post("/campanha/anotacoes", {
                "titulo": titulo, "conteudo": conteudo or None,
                "municipio_cod": int(municipio_cod) or None,
                "zona_numero": int(zona) or None, "bairro": bairro or None,
                "tags": tags,
            })
            st.success("Anotação salva.")
            st.cache_data.clear()
