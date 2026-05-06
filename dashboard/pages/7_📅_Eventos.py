from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import datetime

import pandas as pd
import streamlit as st

from dashboard.api_client import autenticado, get, post
from dashboard.components.theme import brand_bar, empty_state, inject_css

st.set_page_config(page_title="Eventos", page_icon="📅", layout="wide")
inject_css()
brand_bar()
st.title("📅 Eventos da campanha")
st.caption("Agenda com público estimado e status.")

if not autenticado():
    st.warning("Faça login para acessar.")
    st.stop()

tab_lista, tab_novo = st.tabs(["Agenda", "Novo evento"])

with tab_lista:
    with st.spinner("Carregando agenda..."):
        eventos = get("/campanha/eventos")
    if eventos:
        st.caption(f"**{len(eventos)}** evento(s) na agenda")
        st.dataframe(pd.DataFrame(eventos), use_container_width=True, hide_index=True, height=480)
    else:
        empty_state("📅", "Sem eventos na agenda",
                    "Use a aba 'Novo evento' para programar comícios, reuniões ou caminhadas.")

with tab_novo:
    with st.form("novo_evento"):
        titulo = st.text_input("Título*")
        descricao = st.text_area("Descrição")
        c1, c2 = st.columns(2)
        data = c1.date_input("Data", datetime.today())
        hora = c2.time_input("Hora", datetime.now().time())
        local = st.text_input("Local")
        c3, c4 = st.columns(2)
        municipio_cod = c3.number_input("Cod. IBGE município", min_value=0, step=1)
        zona = c4.number_input("Zona", min_value=0, step=1)
        bairro = st.text_input("Bairro")
        publico = st.number_input("Público estimado", min_value=0, step=10)
        status_ev = st.selectbox("Status", ["planejado", "confirmado", "realizado", "cancelado"])
        if st.form_submit_button("Criar"):
            inicio = datetime.combine(data, hora)
            post("/campanha/eventos", {
                "titulo": titulo, "descricao": descricao or None,
                "inicio": inicio.isoformat(),
                "fim": None, "local": local or None,
                "municipio_cod": int(municipio_cod) or None,
                "zona_numero": int(zona) or None, "bairro": bairro or None,
                "publico_estimado": int(publico) or None, "status": status_ev,
            })
            st.success("Evento criado.")
            st.cache_data.clear()
