from __future__ import annotations

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from dashboard.api_client import get
from dashboard.components.mapa_ac import mapa_choropleth
from dashboard.components.theme import (
    brand_bar, candidate_header, empty_state, inject_css, require_login, stat_tile,
)

st.set_page_config(page_title="Fábio Rueda", page_icon="👤", layout="wide")
inject_css()
brand_bar()
require_login()
st.title("👤 Fábio Rueda")
st.caption("Painel do candidato — votação, mapa, seções e análise estratégica.")

candidaturas = get("/candidatos/rueda")
if not candidaturas:
    st.warning("Nenhuma candidatura do Rueda encontrada no banco. Verifique se o ETL foi executado.")
    st.stop()

opt = {f"{c['ano']} · {c['cargo']} · {c['partido_sigla'] or '?'} · {c['total_votos']:,} votos".replace(",", "."): c
       for c in candidaturas}
escolha = st.selectbox("Selecione a candidatura", list(opt.keys()))
sel = opt[escolha]

with st.spinner("Carregando dados da candidatura..."):
    detalhe = get(f"/candidatos/{sel['candidatura_id']}")

candidate_header(detalhe)

aba_zona, aba_mapa, aba_secao, aba_estrategia, aba_partidaria = st.tabs(
    ["📍 Por zona", "🗺️ Mapa", "🔬 Por seção", "🎯 Estratégia", "🏛️ Análise partidária"]
)

# -------------------- Aba 1: Por zona --------------------
with aba_zona:
    df = pd.DataFrame(detalhe["por_zona"])
    if df.empty:
        empty_state("🗳️", "Sem votação registrada",
                    "Esta candidatura não tem votos por zona no banco. "
                    "Verifique se o ETL `etl.load_db` foi executado para o ano correspondente.")
    else:
        st.subheader("Votos por zona eleitoral")
        fig = px.bar(
            df.sort_values("votos", ascending=True),
            x="votos", y="zona_numero",
            color="municipio_nome",
            orientation="h",
            text="votos",
        )
        fig.update_layout(height=600, yaxis_title="Zona", xaxis_title="Votos")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Mapa de penetração no Acre")
        agregado_municipio = (
            df.groupby(["municipio_cod", "municipio_nome"], dropna=False)["votos"]
            .sum().reset_index()
        )
        agregado_municipio["cod_ibge"] = agregado_municipio["municipio_cod"]
        mapa_choropleth(
            agregado_municipio.to_dict(orient="records"),
            titulo=f"Votos do Rueda — {detalhe['ano']} ({detalhe['cargo']})",
        )

        with st.expander("Detalhamento por zona"):
            st.dataframe(df, use_container_width=True)

# -------------------- Aba 2: Mapa do AC --------------------
with aba_mapa:
    try:
        with st.spinner("Carregando locais e seções..."):
            locais = get(f"/candidatos/{sel['candidatura_id']}/locais")
            secoes_dados = get(f"/candidatos/{sel['candidatura_id']}/secoes")
    except Exception as e:
        locais, secoes_dados = [], []
        st.error(f"Não foi possível carregar dados: {e}")

    if not locais:
        empty_state("📍", "Sem dados de local/seção",
                    "Para ver o mapa interativo, execute "
                    "`etl.tse_locais` + `etl.tse_secao` + `etl.load_votacao_secao` "
                    "para o ano da candidatura.")
    else:
        df_l = pd.DataFrame(locais)
        df_s = pd.DataFrame(secoes_dados) if secoes_dados else pd.DataFrame()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total de votos", f"{int(df_l['votos'].sum()):,}".replace(",", "."),
                  help="Soma dos votos do candidato em todos os locais")
        c2.metric("Locais com voto", len(df_l),
                  help="Escolas/prédios onde o candidato recebeu pelo menos 1 voto")
        c3.metric("Seções com voto", len(df_s),
                  help="Urnas (mais granular que local) com pelo menos 1 voto")
        c4.metric("Municípios atingidos", df_l["municipio_cod"].nunique(),
                  help="Quantos dos 22 municípios do AC tiveram voto para este candidato")

        cf1, cf2 = st.columns([1, 2])
        modo = cf1.radio(
            "Granularidade",
            ["Por local", "Por seção"],
            horizontal=True,
            help="Local agrega seções na mesma escola/prédio",
        )
        camadas = cf2.multiselect(
            "Camadas",
            ["Choropleth municipal", "Heatmap", "Pontos"],
            default=["Choropleth municipal", "Heatmap", "Pontos"],
        )

        # ---------- Camada 1: choropleth municipal ----------
        muni_geo = get("/mapa/municipios.geojson")
        agreg_mun = df_l.groupby(["municipio_cod", "municipio_nome"], dropna=False)["votos"].sum().to_dict()
        max_mun = max(agreg_mun.values()) if agreg_mun else 1
        for f in muni_geo["features"]:
            cod = f["properties"]["cod_ibge"]
            v = int(agreg_mun.get(cod, 0))
            t = v / max_mun if max_mun else 0
            # gradiente amarelo → vermelho (alpha cresce com voto)
            r = 255
            g = int(240 - 220 * t)
            b = int(180 - 180 * t)
            a = int(60 + 140 * t) if v > 0 else 30
            f["properties"]["votos"] = v
            f["properties"]["fillColor"] = [r, g, b, a]

        layers = []
        if "Choropleth municipal" in camadas:
            layers.append(pdk.Layer(
                "GeoJsonLayer",
                data=muni_geo,
                get_fill_color="properties.fillColor",
                get_line_color=[80, 80, 80, 200],
                line_width_min_pixels=1,
                stroked=True,
                filled=True,
                pickable=False,  # tooltip dedicado aos pontos
            ))

        # ---------- Pontos (locais ou seções) ----------
        if modo == "Por local":
            pontos = df_l.dropna(subset=["latitude", "longitude"]).copy()
            pontos["label"] = pontos["nome"]
        else:
            if df_s.empty:
                st.warning("Sem dados de seção para esta candidatura.")
                pontos = pd.DataFrame()
            else:
                pontos = df_s.dropna(subset=["latitude", "longitude"]).copy()
                pontos["nome"] = pontos["local_nome"]
                pontos["label"] = pontos.apply(
                    lambda r: f"Zona {int(r['zona_numero'])} · Seção {int(r['nr_secao'])}",
                    axis=1,
                )

        if not pontos.empty:
            pontos["lat"] = pontos["latitude"].astype(float)
            pontos["lon"] = pontos["longitude"].astype(float)
            pontos["votos_int"] = pontos["votos"].astype(int)
            max_v = max(int(pontos["votos"].max()), 1)
            pontos["radius"] = (pontos["votos_int"] / max_v) ** 0.5 * 1500 + 200
            # cor proporcional: laranja → vermelho intenso
            def _cor(v: int) -> list[int]:
                t = v / max_v
                return [220, int(140 - 110 * t), int(40 - 40 * t), 220]
            pontos["fill"] = pontos["votos_int"].map(_cor)

            if "Heatmap" in camadas:
                layers.append(pdk.Layer(
                    "HeatmapLayer",
                    data=pontos,
                    get_position=["lon", "lat"],
                    get_weight="votos_int",
                    radius_pixels=50,
                    intensity=1.0,
                    threshold=0.05,
                    opacity=0.55,
                    pickable=False,
                ))

            if "Pontos" in camadas:
                layers.append(pdk.Layer(
                    "ScatterplotLayer",
                    data=pontos,
                    get_position=["lon", "lat"],
                    get_radius="radius",
                    get_fill_color="fill",
                    get_line_color=[40, 0, 0, 220],
                    line_width_min_pixels=0.5,
                    stroked=True,
                    pickable=True,
                    opacity=0.85,
                ))

        # View centrada no AC inteiro
        view = pdk.ViewState(latitude=-9.0, longitude=-70.5, zoom=5.6, pitch=0)
        tooltip = {
            "html": "<b>{label}</b><br/><b>{nome}</b><br/>{municipio_nome}<br/><b>{votos_int}</b> votos",
            "style": {"backgroundColor": "white", "color": "black", "fontSize": "12px",
                      "border": "1px solid #ccc", "padding": "6px"},
        }
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view,
            tooltip=tooltip,
            map_style=None,  # fundo neutro do deck.gl
        )
        st.pydeck_chart(deck, use_container_width=True, height=620)

        st.caption(
            f"Mostrando {len(pontos):,} {'locais' if modo == 'Por local' else 'seções'} "
            f"com voto. Zoom out: AC inteiro. Use o tooltip para detalhes.".replace(",", ".")
        )

        with st.expander(f"Tabela detalhada — {modo.lower()}"):
            if modo == "Por local":
                st.dataframe(
                    df_l[["nome", "municipio_nome", "endereco", "bairro", "zona_numero", "votos"]].rename(columns={
                        "nome": "Local", "municipio_nome": "Município",
                        "endereco": "Endereço", "bairro": "Bairro",
                        "zona_numero": "Zona", "votos": "Votos",
                    }),
                    use_container_width=True, hide_index=True, height=400,
                )
            else:
                st.dataframe(
                    df_s[["zona_numero", "nr_secao", "municipio_nome", "local_nome", "votos"]].rename(columns={
                        "zona_numero": "Zona", "nr_secao": "Seção",
                        "municipio_nome": "Município", "local_nome": "Local", "votos": "Votos",
                    }),
                    use_container_width=True, hide_index=True, height=400,
                )

# -------------------- Aba 3: Por seção (lista detalhada) --------------------
with aba_secao:
    try:
        secoes = get(f"/candidatos/{sel['candidatura_id']}/secoes")
    except Exception as e:
        secoes = []
        st.error(f"Não foi possível carregar seções: {e}")

    if not secoes:
        st.info("Sem dados de seção para esta candidatura.")
    else:
        df_s = pd.DataFrame(secoes)
        c1, c2, c3 = st.columns(3)
        c1.metric("Seções com voto", len(df_s))
        c2.metric("Soma dos votos", f"{int(df_s['votos'].sum()):,}".replace(",", "."))
        c3.metric("Média/seção", f"{df_s['votos'].mean():.1f}")

        muns = ["(todos)"] + sorted(df_s["municipio_nome"].dropna().unique().tolist())
        mun_filtro = st.selectbox("Filtrar por município", muns)
        view_df = df_s if mun_filtro == "(todos)" else df_s[df_s["municipio_nome"] == mun_filtro]
        st.dataframe(
            view_df[["zona_numero", "nr_secao", "municipio_nome", "local_nome", "votos"]].rename(columns={
                "zona_numero": "Zona", "nr_secao": "Seção", "municipio_nome": "Município",
                "local_nome": "Local", "votos": "Votos",
            }),
            use_container_width=True, hide_index=True, height=500,
        )


# -------------------- Aba 4: Estratégia (Gap Analysis) --------------------
with aba_estrategia:
    with st.expander("💡 **O que é uma 'seção de gap'?** — clique para entender", expanded=False):
        st.markdown(
            """
**Seção de gap** é uma urna eleitoral (escola/sala) onde:
- ✅ O **partido escolhido** (UNIÃO Brasil) **teve voto** no ano de cruzamento (2024) — ou seja, o partido tem capilaridade ali.
- ❌ O **candidato selecionado** (Rueda 2022) recebeu **zero votos**.

**Por que importa?**
Cada seção dessas é uma *oportunidade não convertida* — um lugar onde o partido tem presença mas a sua candidatura não chegou. As lideranças do partido que tiraram votos ali são os **palanqueiros naturais** para a próxima eleição.

**Como ler o mapa abaixo:**
- 🟪 **Cor dos municípios**: roxo mais escuro = mais votos UNIÃO perdidos naquele município.
- ⚫ **Pontos**: cada ponto é um local de votação com seção(ões) de gap. Raio proporcional aos votos do partido ali.
- 🔥 **Heatmap**: densidade dos votos perdidos.
- 🔍 **Selector logo abaixo do mapa**: investigue uma seção específica.
            """
        )

    st.caption(
        "Identifica seções onde a candidatura **selecionada** teve **0 votos**, mas o "
        "**partido escolhido no ano cruzamento** teve voto. "
        "São oportunidades não-convertidas."
    )

    cga, cgb = st.columns(2)
    sigla_partido = cga.selectbox("Partido referência", ["UNIÃO", "PL", "PT", "PP", "PSD", "MDB"], index=0)
    ano_cruz = cgb.selectbox("Ano cruzamento", [2024, 2022, 2020], index=0)

    try:
        with st.spinner("Calculando gap analysis..."):
            gap = get(
                f"/candidatos/{sel['candidatura_id']}/gap-analysis",
                params={"sigla_partido": sigla_partido, "ano_cruzamento": ano_cruz, "top_n": 15},
            )
    except Exception as e:
        st.error(f"Erro: {e}")
        st.stop()

    kpis = gap["kpis"]
    if kpis["secoes_gap"] == 0:
        st.success(
            f"Sem gap detectado: candidatura cobre todas as seções onde o {sigla_partido} "
            f"teve voto em {ano_cruz}."
        )
        st.stop()

    # ---------- KPIs ----------
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Seções gap", f"{kpis['secoes_gap']:,}".replace(",", "."),
              help="Seções com voto do partido sem voto do candidato")
    k2.metric(f"Votos {sigla_partido} {ano_cruz} perdidos", f"{kpis['votos_partido_perdidos']:,}".replace(",", "."))
    k3.metric("Municípios afetados", kpis["municipios_gap"])
    k4.metric("% gap", f"{kpis['pct_gap']}%",
              help="(seções gap) / (seções gap + seções com voto do candidato)")

    # ---------- Recomendações ----------
    st.subheader("📋 Recomendações geradas")
    for r in gap["recomendacoes"]:
        st.info(r)

    st.divider()

    # ---------- Mapa das seções gap ----------
    st.subheader("🗺️ Mapa das seções de gap")
    df_gap = pd.DataFrame(gap["secoes_gap"])
    if not df_gap.empty:
        muni_geo2 = get("/mapa/municipios.geojson")
        # Choropleth: votos UNIÃO perdidos por município
        votos_perd = {m["municipio_cod"]: m["votos_partido_perdidos"]
                      for m in gap["por_municipio"]}
        max_p = max(votos_perd.values()) if votos_perd else 1
        for f in muni_geo2["features"]:
            cod = f["properties"]["cod_ibge"]
            v = votos_perd.get(cod, 0)
            t = v / max_p if max_p else 0
            f["properties"]["votos"] = v
            # azul → roxo intenso (cor diferente do mapa principal)
            f["properties"]["fillColor"] = [
                int(80 + 175 * t), int(40 + 30 * t), int(180 - 80 * t),
                int(50 + 150 * t) if v > 0 else 25,
            ]

        df_pts = df_gap.dropna(subset=["latitude", "longitude"]).copy()
        df_pts["lat"] = df_pts["latitude"].astype(float)
        df_pts["lon"] = df_pts["longitude"].astype(float)
        df_pts["votos"] = df_pts["v_partido"].astype(int)
        df_pts["nome"] = df_pts["local_nome"]
        max_v = max(int(df_pts["votos"].max()), 1)
        df_pts["radius"] = (df_pts["votos"] / max_v) ** 0.5 * 1500 + 200
        df_pts["label"] = df_pts.apply(
            lambda r: f"Zona {int(r['zona_numero'])} · Seção {int(r['nr_secao'])}",
            axis=1,
        )

        layers = [
            pdk.Layer(
                "GeoJsonLayer", data=muni_geo2,
                get_fill_color="properties.fillColor",
                get_line_color=[80, 80, 80, 200],
                line_width_min_pixels=1, stroked=True, filled=True, pickable=False,
            ),
            pdk.Layer(
                "HeatmapLayer", data=df_pts,
                get_position=["lon", "lat"], get_weight="votos",
                radius_pixels=50, intensity=1.0, threshold=0.05, opacity=0.5,
                pickable=False,
            ),
            pdk.Layer(
                "ScatterplotLayer", data=df_pts,
                id="pontos-gap",
                get_position=["lon", "lat"], get_radius="radius",
                get_fill_color=[120, 60, 220, 220],
                get_line_color=[20, 0, 80, 220], line_width_min_pixels=0.5,
                stroked=True, pickable=True, opacity=0.85,
                auto_highlight=True,
            ),
        ]
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=-9.0, longitude=-70.5, zoom=5.6),
            tooltip={
                "html": "<b>{label}</b><br/><b>{nome}</b><br/>{municipio_nome}<br/>"
                        f"<b>{{votos}}</b> votos {sigla_partido} {ano_cruz}<br/>"
                        "<i>👇 clique no ponto para investigar</i>",
                "style": {"backgroundColor": "white", "color": "black",
                          "fontSize": "12px", "border": "1px solid #ccc", "padding": "6px"},
            },
            map_style=None,
        )
        evento = st.pydeck_chart(
            deck,
            use_container_width=True,
            height=560,
            selection_mode="single-object",
            on_select="rerun",
            key="map_estrategia",
        )

        # Captura clique no ponto e sincroniza com o selectbox
        try:
            sel_obj = evento.selection.objects.get("pontos-gap", []) if evento and evento.selection else []
        except Exception:
            sel_obj = []
        if sel_obj:
            obj = sel_obj[0]
            secao_clicada = int(obj.get("secao_id"))
            mun_clicado = obj.get("municipio_nome")
            # registra na session pra os selectboxes lerem
            st.session_state["mun_drill"] = mun_clicado or "(todos)"
            st.session_state["__sec_clicada"] = secao_clicada

    # ---------- Drill-down: investigar uma seção ----------
    st.divider()
    st.subheader("🔎 Investigar uma seção de gap")
    st.caption(
        "Selecione uma seção para ver: votos do candidato no entorno (zona/município), "
        "ranking dele na zona, top 10 candidatos do partido naquela urna e top 5 geral."
    )

    df_idx = df_gap.reset_index(drop=True).copy()
    municipios_gap = ["(todos)"] + sorted(df_idx["municipio_nome"].dropna().unique().tolist())
    cda, cdb = st.columns([1, 3])
    mun_filter = cda.selectbox("Filtrar município", municipios_gap, key="mun_drill")
    if mun_filter != "(todos)":
        df_filtrado = df_idx[df_idx["municipio_nome"] == mun_filter].reset_index(drop=True)
    else:
        df_filtrado = df_idx

    def _label(i: int) -> str:
        r = df_filtrado.iloc[i]
        return (f"{r['municipio_nome']} · Zona {int(r['zona_numero'])} · "
                f"Seção {int(r['nr_secao'])} · {r['local_nome']} "
                f"({int(r['v_partido'])} votos {sigla_partido})")

    if not df_filtrado.empty:
        # Se houve clique no mapa, posicionar selectbox naquela seção
        sec_clicada = st.session_state.pop("__sec_clicada", None)
        idx_inicial = 0
        if sec_clicada is not None:
            match = df_filtrado.index[df_filtrado["secao_id"] == sec_clicada]
            if len(match) > 0:
                idx_inicial = int(match[0])
                # força o selectbox a respeitar o clique
                st.session_state["sec_drill"] = idx_inicial

        sel_idx = cdb.selectbox(
            f"Seção (ordenadas por votos {sigla_partido} {ano_cruz} desc)",
            options=list(range(len(df_filtrado))),
            format_func=_label,
            key="sec_drill",
        )
        sec_row = df_filtrado.iloc[sel_idx]

        det = get(
            f"/secoes/{int(sec_row['zona_numero'])}/{int(sec_row['nr_secao'])}/detalhe-gap",
            params={
                "candidatura_id": sel["candidatura_id"],
                "sigla_partido": sigla_partido,
                "ano_cruzamento": ano_cruz,
            },
        )
        s = det["secao"]
        cref = det["candidato_ref"]

        # Header da seção
        maps_url = (f"https://www.google.com/maps/search/?api=1&query={s['latitude']},{s['longitude']}"
                    if s.get("latitude") else None)
        end_str = s.get("endereco") or "—"
        bairro_str = f" · {s['bairro']}" if s.get("bairro") else ""
        maps_link = f"📍 [Abrir no Google Maps]({maps_url})" if maps_url else ""
        st.markdown(
            f"### 🏫 {s['local_nome']}\n"
            f"**Município**: {s['municipio_nome']} · **Zona** {s['zona_numero']} · **Seção** {s['nr_secao']}  \n"
            f"**Endereço**: {end_str}{bairro_str}  \n"
            f"{maps_link}"
        )

        # KPIs de contexto do Rueda
        st.markdown(f"#### 👤 {cref['nome_urna']} ({cref['ano']} · {cref['cargo']})")
        kk1, kk2, kk3, kk4 = st.columns(4)
        kk1.metric("Aqui (seção)", "0", delta="-gap-",
                   delta_color="inverse",
                   help="Por definição de gap, é zero")
        kk2.metric(f"Na zona {s['zona_numero']}", f"{cref['votos_zona']:,}".replace(",", "."),
                   help="Total de votos do candidato na zona inteira (várias seções)")
        kk3.metric(f"No município", f"{cref['votos_municipio']:,}".replace(",", "."),
                   help=f"Total no município de {s['municipio_nome']}")
        rank = cref.get("ranking_zona")
        total = cref.get("total_candidatos_zona")
        kk4.metric(
            "Ranking na zona",
            f"#{rank}" if rank else "—",
            delta=f"de {total} candidatos {cref['cargo']}" if total else None,
            delta_color="off",
            help=f"Posição entre candidatos a {cref['cargo']} ({cref['ano']}) na zona {s['zona_numero']}",
        )

        # Top partido + top geral lado a lado
        cdt1, cdt2 = st.columns([3, 2])
        with cdt1:
            st.markdown(f"**🤝 Top {sigla_partido} ({ano_cruz}) nesta seção**")
            tp = pd.DataFrame(det["top_partido"])
            if tp.empty:
                st.caption("Sem candidatos do partido nesta seção.")
            else:
                tp_show = tp[["nome_urna", "cargo", "numero", "municipio_nome", "votos", "total_votos"]].copy()
                tp_show.columns = ["Nome de urna", "Cargo", "Nº", "Município", "Votos aqui", "Total candidato"]
                st.dataframe(tp_show, use_container_width=True, hide_index=True, height=320)

        with cdt2:
            st.markdown(f"**🏆 Top geral (qualquer partido, {ano_cruz})**")
            tg = pd.DataFrame(det["top_geral"])
            if tg.empty:
                st.caption("Sem dados.")
            else:
                tg_show = tg[["nome_urna", "partido", "cargo", "votos"]].copy()
                tg_show.columns = ["Nome de urna", "Partido", "Cargo", "Votos aqui"]
                st.dataframe(tg_show, use_container_width=True, hide_index=True, height=320)

        # Insight automático
        if not pd.DataFrame(det["top_partido"]).empty:
            top1 = det["top_partido"][0]
            insight = (
                f"🎯 **Liderança natural do {sigla_partido} aqui**: "
                f"**{top1['nome_urna']}** ({top1['cargo']}, nº {top1['numero']}) "
                f"tirou **{top1['votos']} votos** nesta seção em {ano_cruz}. "
                f"Articulação direta com este nome tem alto potencial de conversão "
                f"do eleitorado da urna."
            )
            st.success(insight)

        if det["top_geral"]:
            top_geral_1 = det["top_geral"][0]
            partido_geral = (top_geral_1.get("partido") or "").upper()
            if partido_geral != sigla_partido.upper():
                adversarios = {"PT", "PSOL", "PCdoB", "PCB", "PSTU"}
                if partido_geral in adversarios:
                    st.warning(
                        f"⚠️ **Adversário forte**: {top_geral_1['nome_urna']} "
                        f"({partido_geral} · {top_geral_1['cargo']}) lidera com "
                        f"{top_geral_1['votos']} votos. Considere atuação direta para neutralizar."
                    )
                else:
                    st.info(
                        f"⚖️ **Possível aliança**: {top_geral_1['nome_urna']} "
                        f"({partido_geral} · {top_geral_1['cargo']}) é o nome mais votado aqui "
                        f"({top_geral_1['votos']} votos). Avalie aproximação institucional."
                    )
    else:
        st.info("Nenhuma seção corresponde ao filtro.")

    st.divider()

    # ---------- Top aliados (UNIÃO) e Top líderes (geral) lado a lado ----------
    st.subheader(f"🤝 Lideranças nas seções de gap ({ano_cruz})")
    cl1, cl2 = st.columns(2)

    with cl1:
        st.markdown(f"**Aliados naturais — {sigla_partido}**")
        df_a = pd.DataFrame(gap["top_aliados"])
        if df_a.empty:
            st.caption(f"Sem candidatos {sigla_partido} com voto nas seções gap.")
        else:
            df_a_show = df_a.assign(
                cobertura=lambda d: (d["votos_no_gap"] / d["votos_totais"].replace(0, 1) * 100).round(1)
            )[["nome_urna", "cargo", "municipio_nome", "votos_no_gap", "secoes_atingidas", "cobertura"]]
            df_a_show.columns = ["Nome de urna", "Cargo", "Município", "Votos no gap", "Seções", "% da própria votação"]
            st.dataframe(df_a_show, use_container_width=True, hide_index=True, height=420)
            st.caption(f"% da própria votação = quanto da votação total daquele candidato veio das suas seções de gap.")

    with cl2:
        st.markdown("**Líderes locais — qualquer partido**")
        df_l = pd.DataFrame(gap["top_lideres"])
        if df_l.empty:
            st.caption("Sem dados.")
        else:
            df_l_show = df_l[["nome_urna", "partido", "cargo", "municipio_nome", "votos_no_gap", "secoes_atingidas"]]
            df_l_show.columns = ["Nome de urna", "Partido", "Cargo", "Município", "Votos no gap", "Seções"]
            st.dataframe(df_l_show, use_container_width=True, hide_index=True, height=420)
            st.caption("Quem domina aquelas seções — potenciais aliados externos ou adversários a neutralizar.")

    st.divider()

    # ---------- Por município: ranking de oportunidades ----------
    st.subheader("📊 Oportunidades por município")
    df_m = pd.DataFrame(gap["por_municipio"])
    if not df_m.empty:
        fig_m = px.bar(
            df_m.sort_values("votos_partido_perdidos"),
            x="votos_partido_perdidos", y="municipio_nome", orientation="h",
            text="votos_partido_perdidos",
            labels={"votos_partido_perdidos": f"Votos {sigla_partido} {ano_cruz} perdidos",
                    "municipio_nome": "Município"},
            color="votos_partido_perdidos", color_continuous_scale="Purples",
        )
        fig_m.update_layout(height=max(400, len(df_m) * 25), showlegend=False)
        st.plotly_chart(fig_m, use_container_width=True)

    with st.expander("Tabela completa das seções gap"):
        df_full = df_gap[["zona_numero", "nr_secao", "municipio_nome", "local_nome",
                          "endereco", "bairro", "v_partido"]].rename(columns={
            "zona_numero": "Zona", "nr_secao": "Seção", "municipio_nome": "Município",
            "local_nome": "Local", "endereco": "Endereço", "bairro": "Bairro",
            "v_partido": f"Votos {sigla_partido} {ano_cruz}",
        })
        st.dataframe(df_full, use_container_width=True, hide_index=True, height=400)


# ==================== Aba 5: Análise partidária ====================
with aba_partidaria:
    with st.spinner("Calculando análise partidária..."):
        ap = get(f"/candidatos/{sel['candidatura_id']}/analise-partidaria")
    ctx = ap["contexto"]

    sub_geral, sub_part, sub_alianca, sub_reg, sub_adv, sub_cad = st.tabs([
        "📊 Visão geral", "🏷️ Por partido", "🤝 Alianças",
        "🗺️ Regional", "⚔️ Adversários", "🪑 Disputa pela cadeira",
    ])

    # ---- Visão geral ----
    with sub_geral:
        st.markdown(
            f"Análise da disputa **{ctx['cargo']} {ctx['ano']}** no Acre, "
            f"com {ctx['cadeiras_disputadas']} cadeiras."
        )
        gc1, gc2, gc3, gc4 = st.columns(4)
        with gc1:
            stat_tile("📊", "Votos válidos no AC",
                      f"{ctx['votos_validos_total']:,}".replace(",", "."),
                      delta=f"todos candidatos {ctx['cargo']}")
        with gc2:
            stat_tile("🪑", "Cadeiras disputadas",
                      str(ctx["cadeiras_disputadas"]),
                      delta=f"{ctx['cargo']} no AC")
        with gc3:
            stat_tile("⚖️", "Coeficiente eleitoral",
                      f"{ctx['coeficiente_eleitoral']:,}".replace(",", "."),
                      delta=f"{ctx['votos_validos_total']:,}/{ctx['cadeiras_disputadas']}".replace(",", "."),
                      variant="accent")
        with gc4:
            stat_tile("🚪", "Mínimo individual",
                      f"{ctx['minimo_individual']:,}".replace(",", "."),
                      delta="10% do coef. eleitoral", variant="warning")

        st.markdown("---")
        st.markdown(f"### Onde está {ctx['candidato_urna']}?")
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            stat_tile("🗳️", "Votos do candidato",
                      f"{ctx['votos_candidato']:,}".replace(",", "."),
                      delta=f"nº {ctx['numero']} · {ctx['partido_sigla']}")
        with rc2:
            atinge = ctx['votos_candidato'] >= ctx['minimo_individual']
            ratio = ctx['votos_candidato'] / ctx['minimo_individual'] if ctx['minimo_individual'] else 0
            stat_tile("✅" if atinge else "❌",
                      "Atinge mínimo individual?",
                      "Sim" if atinge else "Não",
                      delta=f"{ratio:.1f}× o mínimo",
                      variant="success" if atinge else "warning")
        with rc3:
            stat_tile("🏷️", "Coligação", ctx["coligacao"] or "—",
                      delta=ctx["situacao"])

    # ---- Por partido ----
    with sub_part:
        st.markdown("**Ranking de partidos por votação total no AC.** "
                    "Coef. partidário ≥ 1 = partido conquista pelo menos 1 cadeira pelo Quociente Partidário.")
        df_p = pd.DataFrame(ap["partidos"])
        df_p_show = df_p[["sigla", "votos_total", "qt_candidatos", "qt_eleitos",
                          "coef_partidario", "cadeiras_qp", "atinge_clausula", "pct_validos"]].copy()
        df_p_show["atinge_clausula"] = df_p_show["atinge_clausula"].map(
            lambda v: "✅ Sim" if v else "❌ Não")
        df_p_show.columns = [
            "Partido", "Votos", "Candidatos", "Eleitos",
            "Coef. partidário", "Cadeiras (QP)", "Atinge cláusula", "% válidos",
        ]
        max_v = max(int(df_p["votos_total"].max()), 1)
        st.dataframe(
            df_p_show, use_container_width=True, hide_index=True, height=520,
            column_config={
                "Votos": st.column_config.ProgressColumn(
                    "Votos", format="%d", min_value=0, max_value=max_v,
                ),
                "Coef. partidário": st.column_config.NumberColumn(format="%.3f"),
                "% válidos": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

        # Highlight do partido do Rueda
        mine = df_p[df_p["sigla"] == ctx["partido_sigla"]].iloc[0] if not df_p.empty else None
        if mine is not None:
            st.info(
                f"🎯 **{ctx['partido_sigla']}** teve **{int(mine['votos_total']):,} votos** "
                f"({mine['pct_validos']:.1f}% dos válidos), com coef. partidário "
                f"**{mine['coef_partidario']:.3f}** → **{int(mine['cadeiras_qp'])} cadeira(s)** "
                f"pelo QP. {int(mine['qt_candidatos'])} candidatos no total, "
                f"**{int(mine['qt_eleitos'])} eleitos**.".replace(",", ".")
            )

        # Gráfico de barras
        fig_p = px.bar(
            df_p.head(15).sort_values("votos_total"),
            x="votos_total", y="sigla", orientation="h",
            color="cadeiras_qp",
            color_continuous_scale="Blues",
            text="votos_total",
            labels={"votos_total": "Votos", "sigla": ""},
        )
        fig_p.update_layout(height=480)
        st.plotly_chart(fig_p, use_container_width=True)

    # ---- Alianças/Federações ----
    with sub_alianca:
        st.markdown("**Coligações e federações na disputa.** "
                    "Federações funcionam como um único partido para o coeficiente.")
        df_f = pd.DataFrame(ap["federacoes"])
        if df_f.empty:
            empty_state("🤝", "Sem coligações", "Todos os partidos vieram isolados nesta eleição.")
        else:
            max_vf = max(int(df_f["votos_total"].max()), 1)
            df_f_show = df_f[["coligacao", "partidos_siglas", "votos_total",
                              "qt_candidatos", "qt_eleitos", "coef_partidario", "cadeiras_qp"]].copy()
            df_f_show.columns = ["Coligação", "Partidos", "Votos", "Cands", "Eleitos",
                                 "Coef. partidário", "Cadeiras (QP)"]
            st.dataframe(
                df_f_show, use_container_width=True, hide_index=True, height=400,
                column_config={
                    "Votos": st.column_config.ProgressColumn(
                        "Votos", format="%d", min_value=0, max_value=max_vf,
                    ),
                    "Coef. partidário": st.column_config.NumberColumn(format="%.3f"),
                },
            )

    # ---- Regional ----
    with sub_reg:
        st.markdown("**Partido dominante por município** — onde cada legenda é mais forte.")
        df_r = pd.DataFrame(ap["regional"])
        if df_r.empty:
            empty_state("🗺️", "Sem dados regionais", "")
        else:
            df_r_show = df_r[["municipio_nome", "partido_dominante", "votos"]].copy()
            df_r_show.columns = ["Município", "Partido dominante", "Votos do líder"]
            st.dataframe(df_r_show, use_container_width=True, hide_index=True, height=520)

            # Pie por partido dominante (quantos municípios cada partido domina)
            dom = df_r.groupby("partido_dominante").size().reset_index(name="qt")
            fig_r = px.pie(dom, names="partido_dominante", values="qt",
                           title="Em quantos municípios cada partido é dominante",
                           hole=0.45)
            st.plotly_chart(fig_r, use_container_width=True)

    # ---- Adversários ----
    with sub_adv:
        st.markdown(f"**Os 15 candidatos mais próximos de {ctx['candidato_urna']} em votação.** "
                    "Estes são os adversários diretos pela mesma cadeira.")
        df_a = pd.DataFrame(ap["adversarios"])
        df_a_show = df_a[["posicao", "nome_urna", "partido", "coligacao",
                          "numero", "total_votos", "situacao", "distancia"]].copy()
        df_a_show.columns = ["Pos.", "Nome de urna", "Partido", "Coligação",
                             "Nº", "Votos", "Situação", "Distância"]
        st.dataframe(df_a_show, use_container_width=True, hide_index=True, height=540)

        st.markdown("---")
        st.markdown("**Co-partidários** — concorrência interna no UNIÃO Brasil:")
        df_i = pd.DataFrame(ap["internos_partido"])
        df_i_show = df_i[["rank_partido", "nome_urna", "numero", "total_votos", "situacao"]].copy()
        df_i_show.columns = ["Rank no partido", "Nome de urna", "Nº", "Votos", "Situação"]
        st.dataframe(df_i_show, use_container_width=True, hide_index=True, height=380)
        rank_r = ap.get("rueda_rank_partido")
        if rank_r:
            st.info(f"🎯 {ctx['candidato_urna']} foi o **#{rank_r}** dentro do {ctx['partido_sigla']}.")

    # ---- Disputa pela cadeira ----
    with sub_cad:
        st.markdown("**Análise da disputa pela cadeira** — quanto falta para virar eleito.")
        d = ap["disputa_cadeira"]

        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            stat_tile("🏁", "Posição geral",
                      f"#{d['posicao_geral']}" if d["posicao_geral"] else "—",
                      delta=f"em {len(ap['adversarios']) if ap['adversarios'] else '?'} candidatos próximos")
        with dc2:
            stat_tile("🪑", "Último eleito teve",
                      f"{d['ultimo_eleito_votos']:,}".replace(",", "."),
                      delta=f"{d['delta_ultimo_eleito']:+,} para você atingir".replace(",", "."),
                      variant="warning" if d["delta_ultimo_eleito"] > 0 else "success")
        with dc3:
            stat_tile("📍", "Primeiro suplente",
                      f"{d['primeiro_suplente_votos']:,}".replace(",", "."),
                      delta="próximo da linha de corte")

        # Insights estratégicos
        if not d["atinge_minimo"]:
            st.error(
                f"❌ **{ctx['candidato_urna']} não atinge o mínimo individual** "
                f"({d['minimo_individual']:,} votos). Faltam **{abs(d['delta_minimo']):,}** "
                f"para entrar no rol elegível pelo TSE.".replace(",", ".")
            )
        else:
            ratio = d["votos_candidato"] / d["minimo_individual"]
            st.success(
                f"✅ **{ctx['candidato_urna']} atinge o mínimo individual** "
                f"({d['minimo_individual']:,} votos) — está com {ratio:.2f}× o mínimo.".replace(",", ".")
            )

        if d["delta_ultimo_eleito"] > 0:
            st.warning(
                f"⚠️ Para virar eleito direto, precisa de mais **{d['delta_ultimo_eleito']:,}** votos "
                f"do que o último eleito ({d['ultimo_eleito_votos']:,} votos). "
                "Sobras podem ajudar — avalie cenário do partido na aba 'Por partido'.".replace(",", ".")
            )

        # Comparativo evolução do partido 2022 → 2024
        evo = ap.get("evolucao_partido_2022_2024", [])
        if evo and len(evo) >= 2:
            st.markdown("---")
            st.markdown(f"**Evolução {ctx['partido_sigla']}: 2022 → 2024**")
            df_e = pd.DataFrame(evo)
            v_2022 = int(df_e[df_e["ano"] == 2022]["total"].sum() or 0)
            v_2024 = int(df_e[df_e["ano"] == 2024]["total"].sum() or 0)
            delta = v_2024 - v_2022
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                stat_tile("📊", "Total 2022", f"{v_2022:,}".replace(",", "."))
            with ec2:
                stat_tile("📊", "Total 2024", f"{v_2024:,}".replace(",", "."))
            with ec3:
                pct = (delta / v_2022 * 100) if v_2022 else 0
                stat_tile("📈", "Variação",
                          f"{delta:+,}".replace(",", "."),
                          delta=f"{pct:+.1f}%",
                          variant="success" if delta > 0 else "warning")
            st.caption("Atenção: 2022 são cargos federais/estaduais; 2024 são municipais — "
                       "comparação de tendência partidária, não direta.")
