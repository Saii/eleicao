"""
Entry-point do Dashboard Campanha AC.
Rode: streamlit run dashboard/app.py
"""
from __future__ import annotations

# bootstrap: insere a raiz do projeto no sys.path para resolver imports `dashboard.*`
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from dashboard.api_client import autenticado, get, login, logout
from dashboard.components.theme import (
    action_card,
    brand_bar,
    hero,
    inject_css,
    stat_tile,
)

st.set_page_config(
    page_title="Campanha AC — Fábio Rueda",
    page_icon="🗳️",
    layout="wide",
)
inject_css()
brand_bar()


# ---------- Sidebar reorganizada ----------
with st.sidebar:
    st.markdown("### 📊 Análise eleitoral")
    st.page_link("pages/1_🗺️_Mapa.py", label="Mapa do Acre", icon="🗺️")
    st.page_link("pages/2_👤_Rueda.py", label="Fábio Rueda", icon="👤")
    st.page_link("pages/3_🔍_Buscar.py", label="Buscar candidato", icon="🔍")
    st.page_link("pages/4_🏛️_Partido.py", label="Por partido", icon="🏛️")
    st.page_link("pages/5_⚖️_Comparador.py", label="Comparador", icon="⚖️")
    st.page_link("pages/10_📍_Locais.py", label="Locais de votação", icon="📍")

    st.markdown("### 🗂️ Gestão de campanha")
    st.page_link("pages/6_👥_Apoiadores.py", label="Apoiadores", icon="👥")
    st.page_link("pages/7_📅_Eventos.py", label="Eventos", icon="📅")
    st.page_link("pages/8_📝_Anotações.py", label="Anotações", icon="📝")
    st.page_link("pages/9_🎯_Metas.py", label="Metas", icon="🎯")

    st.markdown("### 👤 Conta")
    if autenticado():
        st.success("✅ Autenticado", icon="🔓")
        if st.button("Sair", use_container_width=True):
            logout()
            st.rerun()
    else:
        with st.form("login", border=False):
            email = st.text_input("E-mail", placeholder="seu@email.com")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                if login(email, senha):
                    st.rerun()
                else:
                    st.error("Credenciais inválidas")
        st.caption("Login necessário para módulos de gestão.")

    st.markdown(
        '<div style="margin-top:2rem;padding-top:1rem;border-top:1px solid #E5E7EB;'
        'font-size:0.7rem;color:#9CA3AF;">'
        "Fontes: TSE · IBGE<br/>"
        "Atualizado em 2026-05-05"
        "</div>",
        unsafe_allow_html=True,
    )


# ---------- Hero ----------
hero(
    "Fábio Rueda · Campanha 2026",
    "Análise eleitoral e gestão de campanha · Estado do Acre",
)


# ---------- Status executivo ----------
st.markdown("### 📈 Status da campanha")


@st.cache_data(ttl=30)
def _kpi_eleitoral():
    try:
        rueda_cands = get("/candidatos/rueda")
        rueda_total_votos = sum(c.get("total_votos", 0) for c in rueda_cands)
        filiacao = get("/partidos/UNIÃO/filiacao")
        gap = None
        if rueda_cands:
            cid = rueda_cands[0]["candidatura_id"]
            gap = get(f"/candidatos/{cid}/gap-analysis", params={"top_n": 1})
        return {
            "candidaturas": len(rueda_cands),
            "votos_rueda": rueda_total_votos,
            "filiados_uniao": filiacao.get("total", 0),
            "secoes_gap": gap["kpis"]["secoes_gap"] if gap else 0,
            "votos_perdidos": gap["kpis"]["votos_partido_perdidos"] if gap else 0,
            "municipios_gap": gap["kpis"]["municipios_gap"] if gap else 0,
        }
    except Exception:
        return None


@st.cache_data(ttl=10)
def _kpi_campanha():
    """Só roda se autenticado."""
    if not autenticado():
        return None
    try:
        apoiadores = get("/campanha/apoiadores") or []
        eventos = get("/campanha/eventos") or []
        metas = get("/campanha/metas") or []
        anotacoes = get("/campanha/anotacoes") or []

        agora = datetime.now(timezone.utc)
        eventos_futuros = [
            e for e in eventos if e.get("inicio") and e.get("status") not in ("realizado", "cancelado")
            and datetime.fromisoformat(e["inicio"].replace("Z", "+00:00")) > agora
        ]
        metas_em_andamento = [m for m in metas if m.get("status") in ("aberta", "em_andamento")]
        metas_atingidas = [m for m in metas if m.get("status") == "atingida"]

        municipios_apoiadores = len({a.get("municipio_cod") for a in apoiadores if a.get("municipio_cod")})

        return {
            "apoiadores": len(apoiadores),
            "eventos_futuros": len(eventos_futuros),
            "eventos_total": len(eventos),
            "metas_andamento": len(metas_em_andamento),
            "metas_atingidas": len(metas_atingidas),
            "metas_total": len(metas),
            "anotacoes": len(anotacoes),
            "municipios_apoiadores": municipios_apoiadores,
            "apoiadores_data": apoiadores,
        }
    except Exception:
        return None


kpi_e = _kpi_eleitoral()
kpi_c = _kpi_campanha()

if kpi_e:
    # Linha 1: KPIs eleitorais (públicos)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat_tile("🗳️", "Candidaturas Rueda", str(kpi_e["candidaturas"]),
                  delta="histórico TSE")
    with c2:
        stat_tile("📊", "Votos totais", f"{kpi_e['votos_rueda']:,}".replace(",", "."),
                  delta="todas as candidaturas")
    with c3:
        stat_tile("🏷️", "Filiados UNIÃO/AC",
                  f"{kpi_e['filiados_uniao']:,}".replace(",", "."),
                  delta="snapshot 2026", variant="accent")
    with c4:
        stat_tile("🎯", "Seções de gap", f"{kpi_e['secoes_gap']:,}".replace(",", "."),
                  delta=f"{kpi_e['votos_perdidos']:,} votos · {kpi_e['municipios_gap']} municípios".replace(",", "."),
                  variant="warning")
else:
    st.warning("⚠️ API offline — verifique se `uvicorn api.main:app` está rodando na porta 8000.")

if kpi_c:
    st.markdown("#### 🗂️ Operação da campanha")
    cc1, cc2, cc3, cc4 = st.columns(4)
    with cc1:
        stat_tile("👥", "Apoiadores", str(kpi_c["apoiadores"]),
                  delta=f"em {kpi_c['municipios_apoiadores']} municípios")
    with cc2:
        stat_tile("📅", "Eventos futuros", str(kpi_c["eventos_futuros"]),
                  delta=f"de {kpi_c['eventos_total']} totais", variant="accent")
    with cc3:
        delta_m = (
            f"{kpi_c['metas_atingidas']}/{kpi_c['metas_total']} atingidas"
            if kpi_c["metas_total"] else "nenhuma definida"
        )
        stat_tile("🎯", "Metas em andamento", str(kpi_c["metas_andamento"]),
                  delta=delta_m, variant="success" if kpi_c["metas_atingidas"] else "")
    with cc4:
        stat_tile("📝", "Anotações", str(kpi_c["anotacoes"]),
                  delta="notas territoriais")

    # Mini gráfico: apoiadores por município
    if kpi_c["apoiadores"]:
        st.markdown("##### Apoiadores por município")
        df_a = pd.DataFrame(kpi_c["apoiadores_data"])
        if "municipio_cod" in df_a.columns:
            agg = (
                df_a[df_a["municipio_cod"].notna()]
                .groupby("municipio_cod").size()
                .reset_index(name="qt")
                .sort_values("qt", ascending=False)
                .head(10)
            )
            if not agg.empty:
                # Tenta resolver nome via API de municípios (cache)
                try:
                    mun_geo = get("/mapa/municipios.geojson")
                    nome_por_cod = {f["properties"]["cod_ibge"]: f["properties"]["nome"]
                                    for f in mun_geo["features"]}
                    agg["municipio"] = agg["municipio_cod"].map(nome_por_cod)
                except Exception:
                    agg["municipio"] = agg["municipio_cod"].astype(str)
                max_a = max(int(agg["qt"].max()), 1)
                st.dataframe(
                    agg[["municipio", "qt"]],
                    use_container_width=True, hide_index=True, height=240,
                    column_config={
                        "municipio": st.column_config.TextColumn("Município"),
                        "qt": st.column_config.ProgressColumn(
                            "Apoiadores", format="%d", min_value=0, max_value=max_a,
                        ),
                    },
                )
elif autenticado():
    st.info("Sem dados de campanha ainda. Use as páginas de gestão para começar.")


# ---------- Ações rápidas ----------
st.markdown("### Ações rápidas")
ac1, ac2, ac3 = st.columns(3)
with ac1:
    action_card("🗺️", "Explorar o mapa", "Votação por município, zona e seção em todo o Acre.")
    st.page_link("pages/1_🗺️_Mapa.py", label="Abrir mapa")
with ac2:
    action_card("🎯", "Análise estratégica", "Identifique seções de gap e lideranças locais para articulação.")
    st.page_link("pages/2_👤_Rueda.py", label="Abrir painel Rueda")
with ac3:
    action_card("👥", "Cadastrar apoiador", "Registre apoiadores da campanha por município e zona.")
    st.page_link("pages/6_👥_Apoiadores.py", label="Abrir cadastro")


# ---------- Bloco final: como começar ----------
with st.expander("ℹ️ Como navegar neste dashboard"):
    st.markdown(
        """
**Análise eleitoral** (público) — explora os resultados das eleições 2020/2022/2024 no AC.

- **Mapa do Acre**: choropleth por município com filtros de cargo e partido.
- **Fábio Rueda**: painel completo do candidato com mapa, drill-down por seção e análise estratégica de gap.
- **Buscar candidato**: pesquise qualquer candidato do banco (4.500+ pessoas).
- **Por partido**: visão agregada com lista de candidatos e perfil de filiação.
- **Comparador**: compare dois ou mais candidatos lado a lado.
- **Locais de votação**: 670 escolas/prédios mapeados em 2024.

**Gestão de campanha** (login obrigatório) — CRUD da operação.

- **Apoiadores**: cadastro segmentado por município/zona/bairro.
- **Eventos**: agenda com público estimado e status.
- **Anotações**: notas territoriais com tags.
- **Metas**: votos-alvo por região e prazo.
        """
    )
