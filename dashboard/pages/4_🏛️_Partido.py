from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import get
from dashboard.components.mapa_ac import mapa_choropleth
from dashboard.components.theme import brand_bar, empty_state, inject_css, require_login

st.set_page_config(page_title="Por partido", page_icon="🏛️", layout="wide")
inject_css()
brand_bar()
require_login()
st.title("🏛️ Visão por partido")
st.caption("Votação, candidatos e perfil de filiação agregado.")

partidos = get("/partidos")
opcoes = {f"{p['sigla']} — {p['nome']}": p["sigla"] for p in partidos}

c1, c2 = st.columns(2)
default_sigla_idx = next((i for i, k in enumerate(opcoes) if k.startswith("UNIÃO")), 0)
sigla_label = c1.selectbox("Partido", list(opcoes.keys()), index=default_sigla_idx)
ano = c2.selectbox("Ano", [2024, 2022, 2020])
sigla = opcoes[sigla_label]

aba_votos, aba_candidatos, aba_filiacao = st.tabs(["📊 Votação", "👥 Candidatos", "🏷️ Filiação"])

# -------------------- Aba 1: Votação --------------------
with aba_votos:
    dados = get(f"/partidos/{sigla}/agregado", params={"ano": ano})
    st.metric(f"Total de votos {sigla} em {ano}",
              f"{dados['total']:,}".replace(",", "."),
              help="Soma de todos os candidatos da legenda em todos os cargos do ano")

    df = pd.DataFrame(dados["municipios"])
    if df.empty:
        st.info("Sem dados.")
    else:
        fig = px.bar(df.sort_values("votos"), x="votos", y="municipio", orientation="h")
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        mapa_choropleth(df.to_dict(orient="records"), titulo=f"Votos {sigla} — {ano}")

# -------------------- Aba 2: Candidatos --------------------
with aba_candidatos:
    cargos = get("/candidatos/cargos", params={"ano": ano})
    cc1, cc2 = st.columns([3, 1])
    cargo_sel = cc1.selectbox("Cargo", ["(todos)"] + cargos)
    apenas_eleitos = cc2.checkbox("Apenas eleitos", value=False)

    params: dict = {"ano": ano, "limit": 500, "apenas_eleitos": apenas_eleitos}
    if cargo_sel != "(todos)":
        params["cargo"] = cargo_sel

    with st.spinner(f"Carregando candidatos {sigla}..."):
        candidatos = get(f"/partidos/{sigla}/candidatos", params=params)
    st.caption(f"**{len(candidatos)}** candidatura(s) encontrada(s) · {sigla} · {ano}")

    if candidatos:
        dfc = pd.DataFrame(candidatos)
        max_v_c = max(int(dfc["total_votos"].max()), 1)
        st.dataframe(
            dfc[["nome_urna", "nome", "cargo", "numero", "total_votos"]],
            use_container_width=True,
            hide_index=True,
            height=500,
            column_config={
                "nome_urna": st.column_config.TextColumn("Nome de urna", width="medium"),
                "nome": st.column_config.TextColumn("Nome completo", width="large"),
                "cargo": st.column_config.TextColumn("Cargo", width="small"),
                "numero": st.column_config.NumberColumn("Nº", format="%d", width="small"),
                "total_votos": st.column_config.ProgressColumn(
                    "Votos", format="%d", min_value=0, max_value=max_v_c,
                ),
            },
        )
    else:
        empty_state("🏛️", "Sem candidatos para o filtro",
                    f"Nenhum candidato do {sigla} em {ano} para esse cargo. "
                    "Tente outro cargo ou desmarque 'apenas eleitos'.")

# -------------------- Aba 3: Filiação --------------------
with aba_filiacao:
    try:
        fil = get(f"/partidos/{sigla}/filiacao")
    except Exception as e:
        st.error(f"Não foi possível carregar dados de filiação: {e}")
        fil = None

    if not fil or fil.get("total", 0) == 0:
        empty_state("🏷️", "Sem dados de filiação carregados",
                    "Execute `python -m etl.tse_filiados` seguido de `python -m etl.load_filiacao` "
                    "para popular esta visão. Os dados são agregados (LGPD — sem nomes).")
    else:
        ref = str(fil.get("ref") or "")
        ref_fmt = f"{ref[:4]}/{ref[4:]}" if len(ref) == 6 else ref
        st.caption(f"Snapshot TSE · referência {ref_fmt} · dados agregados (LGPD — sem nomes)")
        st.metric(f"Filiados {sigla}", f"{fil['total']:,}".replace(",", "."),
                  help="Total agregado de filiados ao partido no AC (snapshot TSE, sem nomes por LGPD)")

        f1, f2 = st.columns(2)
        with f1:
            df_mun = pd.DataFrame(fil["por_municipio"])
            if not df_mun.empty:
                df_mun["cod_ibge"] = df_mun["municipio_cod"]
                df_mun["votos"] = df_mun["qt_filiado"]  # alias para o componente
                mapa_choropleth(df_mun.to_dict(orient="records"),
                                titulo=f"Filiados {sigla} por município")
        with f2:
            df_gen = pd.DataFrame(fil["por_genero"])
            if not df_gen.empty:
                fig_g = px.pie(df_gen, names="chave", values="qt", title="Gênero")
                st.plotly_chart(fig_g, use_container_width=True)

            df_idade = pd.DataFrame(fil["por_faixa_etaria"])
            if not df_idade.empty:
                fig_i = px.bar(df_idade, x="chave", y="qt", title="Faixa etária")
                fig_i.update_layout(xaxis_title="", yaxis_title="filiados")
                st.plotly_chart(fig_i, use_container_width=True)

        st.subheader("Filiados por município")
        df_mun_show = pd.DataFrame(fil["por_municipio"])
        if not df_mun_show.empty:
            max_f = max(int(df_mun_show["qt_filiado"].max()), 1)
            st.dataframe(
                df_mun_show[["municipio_nome", "qt_filiado"]],
                use_container_width=True, hide_index=True, height=420,
                column_config={
                    "municipio_nome": st.column_config.TextColumn("Município", width="large"),
                    "qt_filiado": st.column_config.ProgressColumn(
                        "Filiados", format="%d", min_value=0, max_value=max_f,
                    ),
                },
            )
