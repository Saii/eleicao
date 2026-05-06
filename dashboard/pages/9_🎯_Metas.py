from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import autenticado, get, post
from dashboard.components.theme import brand_bar, empty_state, inject_css, stat_tile

st.set_page_config(page_title="Metas", page_icon="🎯", layout="wide")
inject_css()
brand_bar()
st.title("🎯 Metas — 40 mil votos no Acre")
st.caption("Decomposição estratégica, projeção, cenários e plano de ação para Deputado Federal 2026.")

if not autenticado():
    empty_state("🔐", "Login necessário",
                "Faça login na página inicial para acessar o módulo de Metas.")
    st.stop()


# ---------- Sidebar de cenário ----------
with st.sidebar:
    st.markdown("### ⚙️ Configuração de cenário")
    try:
        cenarios_disp = get("/metas-avancado/cenarios")
        nomes = [c["nome"] for c in cenarios_disp]
    except Exception:
        cenarios_disp, nomes = [], ["realista", "conservador"]
    cenario_sel = st.selectbox(
        "Cenário ativo", nomes,
        index=nomes.index("realista") if "realista" in nomes else 0,
        help="Realista usa multiplicadores de literatura. Conservador é mais cauteloso.",
    )
    cen_info = next((c for c in cenarios_disp if c["nome"] == cenario_sel), None)
    if cen_info:
        st.caption(cen_info.get("descricao", ""))
        st.markdown(
            f"**Multiplicadores:**  \n"
            f"Lead (n1): `{cen_info['m_nivel_1']}`  ·  "
            f"Apoiador (n2): `{cen_info['m_nivel_2']}`  \n"
            f"Militante (n3): `{cen_info['m_nivel_3']}`  ·  "
            f"Liderança (n4): `{cen_info['m_nivel_4']}`  \n"
            f"Decay: `{cen_info['decay_temporal']}` · "
            f"Retenção histórica: `{cen_info['retencao_historica']}`"
        )


# ---------- Setup inicial (se meta-mãe não existe) ----------
try:
    dash = get("/metas-avancado/dashboard", params={"cenario": cenario_sel})
except Exception as e:
    if "404" in str(e) or "não configurada" in str(e):
        st.warning("Meta-mãe ainda não configurada.")
        c1, c2 = st.columns(2)
        votos_alvo = c1.number_input("Meta total de votos", min_value=1000, value=40000, step=1000)
        if c2.button("🚀 Configurar meta-mãe e distribuir nos 22 municípios", type="primary"):
            with st.spinner("Distribuindo meta..."):
                post("/metas-avancado/setup-meta-mae", {})
                st.cache_data.clear()
                st.rerun()
        st.stop()
    else:
        st.error(f"Erro ao carregar dashboard: {e}")
        st.stop()


abas = st.tabs([
    "🎯 Meta-mãe",
    "🗺️ Por território",
    "👥 Por canal",
    "🔮 Cenários",
    "📋 Plano de ação",
    "📈 Histórico",
    "🎲 Probabilidade",
])

mae = dash["meta_mae"]
kp = dash["kpis"]

# -------------------- Aba 1: Meta-mãe --------------------
with abas[0]:
    g1, g2 = st.columns([2, 3])
    with g1:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=kp["votos_projetados"],
            number={"suffix": " votos", "valueformat": ",.0f"},
            delta={"reference": mae["votos_alvo"], "relative": False, "valueformat": ",.0f"},
            gauge={
                "axis": {"range": [0, mae["votos_alvo"] * 1.1], "tickformat": ",.0f"},
                "bar": {"color": "#003087"},
                "steps": [
                    {"range": [0, mae["votos_alvo"] * 0.5], "color": "#FEE2E2"},
                    {"range": [mae["votos_alvo"] * 0.5, mae["votos_alvo"] * 0.85], "color": "#FEF3C7"},
                    {"range": [mae["votos_alvo"] * 0.85, mae["votos_alvo"]], "color": "#D1FAE5"},
                ],
                "threshold": {"line": {"color": "#FF6B00", "width": 4},
                              "thickness": 0.85, "value": mae["votos_alvo"]},
            },
            title={"text": f"<b>{mae['cargo']} {mae['ano_alvo']}</b>"},
        ))
        gauge.update_layout(height=360, margin=dict(l=20, r=20, t=60, b=20))
        st.plotly_chart(gauge, use_container_width=True)

    with g2:
        kk1, kk2 = st.columns(2)
        with kk1:
            stat_tile("📊", "Projeção atual",
                      f"{kp['votos_projetados']:,}".replace(",", "."),
                      delta=f"{kp['pct_atingido']}% da meta")
        with kk2:
            stat_tile("📍", "Distância para a meta",
                      f"{kp['distancia_votos']:,}".replace(",", "."),
                      delta="votos a conquistar", variant="warning")
        kk3, kk4 = st.columns(2)
        with kk3:
            stat_tile("👥", "Apoiadores totais", str(kp["apoiadores_total"]),
                      delta=f"em {22 - kp['municipios_sem_apoiador']} de 22 municípios",
                      variant="accent")
        with kk4:
            data_el = datetime.fromisoformat(mae["data_eleicao"]).date()
            dias = (data_el - date.today()).days
            stat_tile("⏱️", "Dias até a eleição", str(max(dias, 0)),
                      delta=f"{kp['pct_tempo_decorrido']}% do tempo decorrido")

        st.markdown("---")
        st.markdown(f"**Cenário em uso**: `{dash['cenario_usado']}` · "
                    f"**Eleição**: {mae['data_eleicao']}")
        if dias > 0:
            votos_dia = kp["distancia_votos"] / dias
            st.markdown(
                f"📈 Para bater a meta no prazo: **{votos_dia:.1f} votos/dia** "
                f"de aumento na projeção."
            )


# -------------------- Aba 2: Por território --------------------
with abas[1]:
    df_filhas = pd.DataFrame(dash["filhas"])
    if df_filhas.empty:
        empty_state("🗺️", "Sem decomposição", "Reconfigure a meta-mãe.")
    else:
        st.markdown("**Distribuição automática dos 40k pelos municípios** "
                    "(peso composto: 50% filiados UNIÃO + 30% capilaridade UNIÃO 2024 + 20% baseline)")

        from dashboard.components.mapa_ac import mapa_choropleth
        df_map = df_filhas.copy()
        df_map["cod_ibge"] = df_map["municipio_cod"]
        df_map["votos"] = df_map["pct"]  # mapa colore por % atingido
        mapa_choropleth(df_map.to_dict(orient="records"),
                        titulo="% da meta atingido por município")

        st.markdown("**Tabela de metas por município**")
        df_show = df_filhas[[
            "municipio_nome", "votos_alvo", "votos_projetados",
            "apoiadores", "pct",
        ]].copy()
        df_show.columns = ["Município", "Meta", "Projetado", "Apoiadores", "% atingido"]
        max_alvo = max(int(df_show["Meta"].max()), 1)
        st.dataframe(
            df_show, use_container_width=True, hide_index=True, height=520,
            column_config={
                "Meta": st.column_config.ProgressColumn(
                    "Meta (votos)", format="%d", min_value=0, max_value=max_alvo,
                ),
                "Projetado": st.column_config.NumberColumn(format="%d"),
                "Apoiadores": st.column_config.NumberColumn(format="%d"),
                "% atingido": st.column_config.ProgressColumn(
                    "% da meta", format="%.1f%%", min_value=0, max_value=100,
                ),
            },
        )

        # Gap por município (gráfico)
        st.markdown("**Gap por município (votos faltando)**")
        df_filhas["gap"] = df_filhas["votos_alvo"] - df_filhas["votos_projetados"]
        df_gap = df_filhas[df_filhas["gap"] > 0].sort_values("gap", ascending=False).head(15)
        fig_gap = px.bar(df_gap, x="gap", y="municipio_nome", orientation="h",
                         color="gap", color_continuous_scale="Reds",
                         labels={"gap": "Votos faltando", "municipio_nome": ""})
        fig_gap.update_layout(height=480, showlegend=False)
        st.plotly_chart(fig_gap, use_container_width=True)


# -------------------- Aba 3: Por canal --------------------
with abas[2]:
    st.markdown("**Decomposição dos votos projetados por canal de origem**")

    df_canal = pd.DataFrame(dash["filhas"])
    if df_canal.empty:
        empty_state("👥", "Sem dados", "Configure a meta-mãe primeiro.")
    else:
        # Soma totais por canal
        org = sum(f["projecao"]["organico"] for f in dash["filhas"])
        evt = sum(f["projecao"]["eventos"] for f in dash["filhas"])
        hist = sum(f["projecao"]["historico"] for f in dash["filhas"])
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            stat_tile("🌱", "Orgânico (apoiadores)", f"{org:,}".replace(",", "."),
                      delta="apoiadores cadastrados × multiplicador",
                      variant="success")
        with cc2:
            stat_tile("📅", "Eventos planejados", f"{evt:,}".replace(",", "."),
                      delta="público estimado × taxa de conversão",
                      variant="accent")
        with cc3:
            stat_tile("🏛️", "Base histórica", f"{hist:,}".replace(",", "."),
                      delta="voto 2022 × retenção",
                      variant="")

        # Donut
        fig_donut = px.pie(
            names=["Orgânico (apoiadores)", "Eventos", "Histórico"],
            values=[org, evt, hist],
            hole=0.55,
            color_discrete_sequence=["#10B981", "#FF6B00", "#003087"],
        )
        fig_donut.update_layout(height=360,
                                title="Composição dos votos projetados")
        st.plotly_chart(fig_donut, use_container_width=True)

        # Pirâmide de apoiadores (precisa buscar no banco)
        st.markdown("**Pirâmide de apoiadores cadastrados**")
        try:
            apoiadores = get("/campanha/apoiadores") or []
            if apoiadores:
                df_a = pd.DataFrame(apoiadores)
                niveis = (
                    df_a.groupby("nivel_engajamento")
                    .size().reset_index(name="qt")
                    .sort_values("nivel_engajamento")
                )
                labels_map = {1: "Lead", 2: "Apoiador", 3: "Militante", 4: "Liderança"}
                niveis["nivel_label"] = niveis["nivel_engajamento"].map(labels_map)
                fig_pir = px.bar(
                    niveis, x="qt", y="nivel_label", orientation="h",
                    color="nivel_engajamento",
                    color_continuous_scale=["#FFE0CC", "#FF6B00", "#003087", "#001F5C"],
                    labels={"qt": "Quantidade", "nivel_label": ""},
                )
                fig_pir.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig_pir, use_container_width=True)
            else:
                empty_state("👥", "Nenhum apoiador cadastrado",
                            "Use a página Apoiadores para começar a captar.")
        except Exception as e:
            st.error(f"Erro carregando apoiadores: {e}")

        st.info(
            "💡 **Cálculo da projeção orgânica**: apoiadores × multiplicador do nível × decay temporal.  \n"
            "Cada lead vale menos que uma liderança (vereador, dirigente). "
            "Acompanhe a Pirâmide para diagnosticar se sua base está só na 'cauda' (lead)."
        )


# -------------------- Aba 4: Cenários what-if --------------------
with abas[3]:
    st.markdown("**Simule diferentes hipóteses ajustando os multiplicadores e fatores.**")
    st.caption("Os parâmetros aqui são experimentais — não alteram o cenário ativo no banco.")

    sl1, sl2 = st.columns(2)
    with sl1:
        m1 = st.slider("Multiplicador Lead (n1)", 0.0, 3.0, 0.5, 0.1,
                       help="Quantos votos cada contato recém-cadastrado vale")
        m2 = st.slider("Multiplicador Apoiador (n2)", 0.5, 5.0, 1.5, 0.1,
                       help="Apoiador típico (puxa cônjuge ou similar)")
        m3 = st.slider("Multiplicador Militante (n3)", 1.0, 15.0, 5.0, 0.5,
                       help="Pessoa engajada (puxa pequena rede)")
        m4 = st.slider("Multiplicador Liderança (n4)", 5.0, 100.0, 30.0, 1.0,
                       help="Vereador/dirigente (alta capilaridade)")
    with sl2:
        fe = st.slider("Conversão de eventos", 0.0, 0.5, 0.20, 0.01,
                       help="% do público estimado que vira voto")
        dt = st.slider("Decay temporal", 0.3, 1.0, 0.65, 0.05,
                       help="Quanto da promessa vira voto na urna meses depois")
        rh = st.slider("Retenção histórica", 0.5, 1.0, 0.85, 0.05,
                       help="% do voto 2022 mantido em 2026")

    if st.button("🔄 Recalcular", type="primary"):
        st.cache_data.clear()
    res = get("/metas-avancado/what-if", params={
        "m_nivel_1": m1, "m_nivel_2": m2, "m_nivel_3": m3, "m_nivel_4": m4,
        "fator_evento": fe, "decay_temporal": dt, "retencao_historica": rh,
    })

    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        stat_tile("📊", "Projeção (custom)",
                  f"{res['votos_projetados']:,}".replace(",", "."),
                  delta=f"{res['pct_atingido']}% da meta")
    with rc2:
        stat_tile("📍", "Distância", f"{res['distancia']:,}".replace(",", "."),
                  variant="warning")
    with rc3:
        delta_vs_atual = res["votos_projetados"] - kp["votos_projetados"]
        sign = "+" if delta_vs_atual >= 0 else ""
        stat_tile("🆚", "vs. cenário ativo",
                  f"{sign}{delta_vs_atual:,}".replace(",", "."),
                  delta=f"comparado a `{cenario_sel}`",
                  variant="success" if delta_vs_atual >= 0 else "warning")

    st.caption(
        "💡 Use os sliders para entender a sensibilidade da projeção. "
        "Pequenos ajustes em `decay_temporal` e `retencao_historica` "
        "podem mover a projeção em milhares de votos."
    )


# -------------------- Aba 5: Plano de ação --------------------
with abas[4]:
    st.markdown("**Recomendações automáticas baseadas em regras + alocação ótima de recursos.**")

    rec = dash.get("recomendacoes", [])
    if not rec:
        st.success("✅ Sem alertas críticos no momento.")
    else:
        for r in rec:
            nivel = r.get("nivel", "info")
            if nivel == "alerta":
                st.warning(r["texto"])
            elif nivel == "sucesso":
                st.success(r["texto"])
            else:
                st.info(r["texto"])

    st.markdown("---")
    st.subheader("🎯 Alocação ótima de novos apoiadores")
    st.caption("Greedy: prioriza municípios com maior gap até esgotar o orçamento de apoiadores.")

    aloc1, aloc2 = st.columns(2)
    apoia_disp = aloc1.number_input(
        "Apoiadores disponíveis para captar", min_value=10, max_value=10000, value=500, step=50,
    )
    nivel_aloc = aloc2.selectbox(
        "Nível de apoiador a alocar",
        options=[1, 2, 3, 4],
        format_func=lambda n: {1: "1 - Lead", 2: "2 - Apoiador", 3: "3 - Militante", 4: "4 - Liderança"}[n],
        index=1,
    )

    aloc = get("/metas-avancado/alocar", params={
        "apoiadores_disponiveis": apoia_disp,
        "nivel": nivel_aloc,
        "cenario": cenario_sel,
    })
    df_aloc = pd.DataFrame(aloc)
    df_aloc = df_aloc[df_aloc["alocacao_apoiadores"] > 0]
    if df_aloc.empty:
        st.info("Nenhuma alocação necessária — todas as metas municipais já estão cobertas.")
    else:
        total_add = int(df_aloc["votos_adicionais"].sum())
        novo_total = kp["votos_projetados"] + total_add
        novo_pct = round(novo_total / mae["votos_alvo"] * 100, 1)
        st.metric(
            "Votos adicionais com essa alocação",
            f"+{total_add:,}".replace(",", "."),
            delta=f"projeção iria para {novo_total:,} ({novo_pct}%)".replace(",", "."),
        )
        st.dataframe(
            df_aloc[["municipio_nome", "votos_alvo", "votos_projetados",
                     "alocacao_apoiadores", "votos_adicionais"]].rename(columns={
                "municipio_nome": "Município", "votos_alvo": "Meta",
                "votos_projetados": "Atual",
                "alocacao_apoiadores": "Apoiadores a alocar",
                "votos_adicionais": "Votos adicionais",
            }),
            use_container_width=True, hide_index=True, height=420,
        )


# -------------------- Aba 6: Histórico --------------------
with abas[5]:
    st.markdown("**Evolução temporal da projeção de votos.**")

    cb1, cb2 = st.columns([1, 4])
    if cb1.button("📸 Salvar snapshot agora", type="primary"):
        with st.spinner("Salvando..."):
            post("/metas-avancado/snapshot", {})
            st.success("Snapshot salvo.")
            st.cache_data.clear()
            st.rerun()
    cb2.caption("Salve snapshots periodicamente (ex: 1×/semana) para construir o burndown. "
                "Em produção, isso pode rodar como cron job.")

    hist = get("/metas-avancado/historico", params={"cenario": cenario_sel})
    if not hist:
        empty_state(
            "📈", "Sem histórico ainda",
            "Clique em '📸 Salvar snapshot agora' para registrar o primeiro ponto. "
            "Repita a cada semana para ver a curva de progresso.",
        )
    else:
        df_h = pd.DataFrame(hist)
        df_h["data"] = pd.to_datetime(df_h["data"])
        # Linha de meta (40k constante)
        df_h["meta"] = mae["votos_alvo"]

        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(x=df_h["data"], y=df_h["votos_projetados"],
                                    mode="lines+markers", name="Projeção",
                                    line=dict(color="#003087", width=3)))
        fig_h.add_trace(go.Scatter(x=df_h["data"], y=df_h["meta"],
                                    mode="lines", name="Meta",
                                    line=dict(color="#FF6B00", width=2, dash="dash")))
        fig_h.update_layout(
            height=420, hovermode="x unified",
            yaxis_title="Votos", xaxis_title="",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_h, use_container_width=True)

        # Velocidade
        if len(df_h) >= 2:
            df_h_sorted = df_h.sort_values("data")
            primeiro = df_h_sorted.iloc[0]
            ultimo = df_h_sorted.iloc[-1]
            dias = max((ultimo["data"] - primeiro["data"]).days, 1)
            delta = ultimo["votos_projetados"] - primeiro["votos_projetados"]
            velocidade = delta / dias
            st.metric(
                "Velocidade de aproximação",
                f"{velocidade:+.1f} votos/dia",
                help="Diferença entre o primeiro e último snapshot, dividido pelos dias",
            )

        st.dataframe(df_h, use_container_width=True, hide_index=True, height=240)


# -------------------- Aba 7: Probabilidade --------------------
with abas[6]:
    st.markdown("**Análise probabilística e validação histórica do modelo.**")

    sub1, sub2 = st.tabs(["🎲 Monte Carlo", "🔁 Backtest 2022"])

    with sub1:
        st.caption("Simula a distribuição de votos finais com ruído gaussiano em torno da projeção. "
                   "Útil para entender o intervalo de confiança.")
        mc1, mc2 = st.columns(2)
        sigma = mc1.slider("Volatilidade (σ relativa)", 0.05, 0.50, 0.20, 0.05,
                           help="Desvio padrão como % da projeção. Maior = mais incerteza")
        n_sim = mc2.select_slider("Nº simulações", options=[1000, 5000, 10000, 25000], value=5000)
        mc = get("/metas-avancado/monte-carlo",
                 params={"cenario": cenario_sel, "sigma": sigma, "n": n_sim})

        c_mc1, c_mc2, c_mc3, c_mc4 = st.columns(4)
        with c_mc1:
            stat_tile("🎯", "Probabilidade de bater meta",
                      f"{mc['prob_atingir']*100:.1f}%",
                      delta=f"em {mc['n']:,} simulações".replace(",", "."),
                      variant="success" if mc["prob_atingir"] > 0.5 else "warning")
        with c_mc2:
            stat_tile("📉", "Cenário pessimista (P10)",
                      f"{mc['p10']:,}".replace(",", "."),
                      delta="10% das simulações abaixo")
        with c_mc3:
            stat_tile("📊", "Mediana (P50)",
                      f"{mc['p50']:,}".replace(",", "."),
                      delta="resultado mais provável", variant="accent")
        with c_mc4:
            stat_tile("📈", "Otimista (P90)",
                      f"{mc['p90']:,}".replace(",", "."),
                      delta="10% das simulações acima")

        # Histograma simulado client-side só para visualização
        import numpy as np
        rng = np.random.default_rng(42)
        amostras = rng.normal(kp["votos_projetados"],
                              kp["votos_projetados"] * sigma, n_sim)
        fig_mc = px.histogram(amostras, nbins=60,
                              labels={"value": "Votos simulados"},
                              color_discrete_sequence=["#003087"])
        fig_mc.add_vline(x=mae["votos_alvo"], line_color="#FF6B00",
                         line_width=3, line_dash="dash",
                         annotation_text="Meta 40k", annotation_position="top")
        fig_mc.add_vline(x=mc["p50"], line_color="#10B981",
                         line_width=2, annotation_text="P50")
        fig_mc.update_layout(height=380, showlegend=False,
                             title="Distribuição das simulações",
                             yaxis_title="Frequência")
        st.plotly_chart(fig_mc, use_container_width=True)

    with sub2:
        st.caption("Aplica o modelo retroativamente sobre Rueda 2022 (12.608 votos reais). "
                   "Ajuste a base de apoiadores hipotéticos da época e veja se o modelo prediz bem.")
        bk1, bk2, bk3, bk4 = st.columns(4)
        n1 = bk1.number_input("Leads (n1)", min_value=0, value=20, step=10)
        n2 = bk2.number_input("Apoiadores (n2)", min_value=0, value=50, step=10)
        n3 = bk3.number_input("Militantes (n3)", min_value=0, value=15, step=5)
        n4 = bk4.number_input("Lideranças (n4)", min_value=0, value=5, step=1)

        bk = get("/metas-avancado/backtest", params={
            "apoiadores_n1": n1, "apoiadores_n2": n2,
            "apoiadores_n3": n3, "apoiadores_n4": n4,
            "cenario": cenario_sel,
        })

        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            stat_tile("🎯", "Real (Rueda 2022)", f"{bk['real']:,}".replace(",", "."),
                      delta="Deputado Federal · UNIÃO")
        with bc2:
            stat_tile("📊", "Previsto pelo modelo",
                      f"{bk['previsto']:,}".replace(",", "."),
                      delta=f"erro: {bk['erro_pct']}%",
                      variant="success" if bk["erro_pct"] < 15 else "warning")
        with bc3:
            stat_tile("📏", "Erro absoluto",
                      f"{bk['erro_abs']:,}".replace(",", "."),
                      delta="quanto o modelo errou")

        if bk["erro_pct"] > 30:
            st.warning("⚠️ Modelo errou bastante — considere ajustar multiplicadores ou cenário.")
        elif bk["erro_pct"] < 10:
            st.success("✅ Modelo bem calibrado para esta combinação de apoiadores.")
        else:
            st.info("ℹ️ Erro moderado. Ajustes finos podem melhorar a precisão.")

