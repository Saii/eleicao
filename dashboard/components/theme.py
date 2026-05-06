"""Estilos visuais compartilhados — paleta UNIÃO Brasil + dark mode + responsivo."""
from __future__ import annotations

import streamlit as st

# Paleta UNIÃO Brasil (referência semântica para Python; CSS abaixo usa variáveis)
AZUL = "#003087"
AZUL_ESCURO = "#001F5C"
LARANJA = "#FF6B00"


_CSS = """
<style>
:root {
    --azul: #003087;
    --azul-escuro: #001F5C;
    --azul-claro: #4263EB;
    --laranja: #FF6B00;
    --laranja-claro: #FFE0CC;
    --bg: #FFFFFF;
    --surface: #FFFFFF;
    --surface-2: #F4F6FB;
    --border: #E5E7EB;
    --text: #1F2937;
    --text-soft: #6B7280;
    --shadow: rgba(0, 0, 0, 0.05);
    --hero-grad: linear-gradient(135deg, #003087 0%, #001F5C 100%);
}

@media (prefers-color-scheme: dark) {
    :root {
        --azul: #4263EB;
        --azul-escuro: #2A3FB0;
        --azul-claro: #6E84F0;
        --laranja: #FF8533;
        --laranja-claro: #4A2410;
        --bg: #0F172A;
        --surface: #1E293B;
        --surface-2: #161E2E;
        --border: #334155;
        --text: #E5E7EB;
        --text-soft: #94A3B8;
        --shadow: rgba(0, 0, 0, 0.3);
        --hero-grad: linear-gradient(135deg, #1E3A8A 0%, #0F1F4F 100%);
    }
}

/* ========== Tipografia base ========== */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

h1 { font-weight: 700 !important; letter-spacing: -0.02em; color: var(--text); }
h2 { font-weight: 700 !important; letter-spacing: -0.01em; color: var(--text); }
h3 { font-weight: 600 !important; color: var(--text); }

/* ========== Métricas como card ========== */
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 4px solid var(--azul);
    border-radius: 8px;
    padding: 14px 18px;
    box-shadow: 0 1px 2px var(--shadow);
    transition: box-shadow 0.15s ease, transform 0.15s ease;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 2px 8px var(--shadow);
    transform: translateY(-1px);
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-soft) !important;
    font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.85rem !important;
    font-weight: 700 !important;
    color: var(--text) !important;
    line-height: 1.2;
}
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* ========== Divisores ========== */
hr { border-color: var(--border) !important; opacity: 0.6; margin: 1.4rem 0 !important; }

/* ========== Tabelas ========== */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}

/* ========== Tabs ========== */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    height: 42px;
    padding: 0 18px;
    font-weight: 500;
    color: var(--text-soft);
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: var(--azul) !important;
    font-weight: 600;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: var(--laranja) !important;
    height: 3px !important;
}

/* ========== Alerts ========== */
[data-testid="stAlert"] { border-radius: 8px; border-left-width: 4px; border-left-style: solid; }

/* ========== Sidebar ========== */
/* Esconde navegação automática do Streamlit (usamos lista custom) */
[data-testid="stSidebarNav"] { display: none !important; }

[data-testid="stSidebar"] {
    background-color: var(--surface-2);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-soft) !important;
    margin-top: 1rem !important;
    margin-bottom: 0.4rem !important;
    font-weight: 700 !important;
}

/* ========== Buttons ========== */
.stButton > button {
    border-radius: 6px;
    font-weight: 500;
    transition: all 0.15s ease;
}
.stButton > button[kind="primary"] {
    background: var(--azul);
    border-color: var(--azul);
}
.stButton > button[kind="primary"]:hover {
    background: var(--azul-escuro);
    border-color: var(--azul-escuro);
}

/* ========== Brand bar (faixa superior fina) ========== */
.brand-bar {
    height: 4px;
    background: linear-gradient(90deg, var(--azul) 0%, var(--azul) 60%, var(--laranja) 60%, var(--laranja) 100%);
    margin: -1rem -1rem 1rem -1rem;
    border-radius: 0;
}

/* ========== Hero card ========== */
.hero-card {
    background: var(--hero-grad);
    color: white;
    padding: 2.4rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.8rem;
    box-shadow: 0 4px 12px rgba(0, 48, 135, 0.18);
    position: relative;
    overflow: hidden;
}
.hero-card::after {
    content: "";
    position: absolute;
    right: -40px;
    top: -40px;
    width: 220px;
    height: 220px;
    background: radial-gradient(circle, rgba(255, 107, 0, 0.18) 0%, transparent 65%);
    pointer-events: none;
}
.hero-card h1 {
    color: white !important;
    font-size: 2.2rem;
    margin: 0 0 0.4rem 0 !important;
    font-weight: 700;
    letter-spacing: -0.02em;
}
.hero-card .tagline { font-size: 1rem; opacity: 0.92; margin: 0; }
.hero-card .accent-bar {
    display: inline-block;
    width: 50px;
    height: 3px;
    background: var(--laranja);
    margin-bottom: 0.8rem;
    border-radius: 2px;
}

/* ========== Action card ========== */
.action-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.4rem 1.2rem;
    height: 100%;
    transition: all 0.15s ease;
}
.action-card:hover {
    border-color: var(--azul);
    box-shadow: 0 2px 8px var(--shadow);
    transform: translateY(-2px);
}
.action-card .icon { font-size: 1.7rem; margin-bottom: 0.5rem; display: block; }
.action-card .title { font-weight: 700; color: var(--text); margin-bottom: 0.2rem; }
.action-card .desc { color: var(--text-soft); font-size: 0.85rem; }

/* ========== Pills/badges ========== */
.pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 4px;
}
.pill-azul { background: var(--azul); color: white; }
.pill-laranja { background: var(--laranja); color: white; }
.pill-cinza { background: var(--border); color: var(--text); }

/* ========== Candidate header card ========== */
.cand-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.4rem;
    display: flex;
    align-items: center;
    gap: 1.4rem;
    box-shadow: 0 1px 3px var(--shadow);
}
.cand-card .avatar {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--hero-grad);
    color: white;
    font-weight: 700;
    font-size: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.cand-card .info { flex: 1; }
.cand-card .nome { font-size: 1.25rem; font-weight: 700; color: var(--text); margin: 0 0 0.2rem 0; }
.cand-card .meta { color: var(--text-soft); font-size: 0.85rem; margin: 0; }
.cand-card .stats {
    display: flex;
    gap: 1.6rem;
    border-left: 1px solid var(--border);
    padding-left: 1.6rem;
}
.cand-card .stat { text-align: center; }
.cand-card .stat-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    color: var(--text-soft);
    letter-spacing: 0.06em;
    font-weight: 600;
}
.cand-card .stat-value { font-size: 1.4rem; font-weight: 700; color: var(--text); margin-top: 0.15rem; }

/* ========== Empty state ========== */
.empty-state {
    text-align: center;
    padding: 3rem 1.5rem;
    background: var(--surface-2);
    border: 2px dashed var(--border);
    border-radius: 12px;
    margin: 1rem 0;
}
.empty-state .icon { font-size: 3rem; opacity: 0.5; display: block; margin-bottom: 0.6rem; }
.empty-state .title { font-size: 1.1rem; font-weight: 600; color: var(--text); margin-bottom: 0.4rem; }
.empty-state .hint { color: var(--text-soft); font-size: 0.9rem; max-width: 400px; margin: 0 auto; }

/* ========== Stat tile (mini KPIs com ícone — dashboard executivo) ========== */
.stat-tile {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    height: 100%;
    display: flex;
    align-items: center;
    gap: 0.9rem;
}
.stat-tile .stat-icon {
    width: 42px;
    height: 42px;
    border-radius: 10px;
    background: var(--surface-2);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
    flex-shrink: 0;
}
.stat-tile .stat-body { flex: 1; min-width: 0; }
.stat-tile .stat-tile-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-soft);
    font-weight: 600;
}
.stat-tile .stat-tile-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
}
.stat-tile .stat-tile-delta { font-size: 0.78rem; color: var(--text-soft); margin-top: 2px; }
.stat-tile.accent { border-left: 4px solid var(--laranja); }
.stat-tile.success { border-left: 4px solid #10B981; }
.stat-tile.warning { border-left: 4px solid #F59E0B; }

/* ========== Responsivo (mobile) ========== */
@media (max-width: 768px) {
    .hero-card { padding: 1.6rem 1.2rem; }
    .hero-card h1 { font-size: 1.5rem; }
    .hero-card .tagline { font-size: 0.85rem; }
    .cand-card {
        flex-direction: column;
        text-align: center;
        gap: 0.9rem;
    }
    .cand-card .stats {
        border-left: none;
        border-top: 1px solid var(--border);
        padding-left: 0;
        padding-top: 0.9rem;
        width: 100%;
        justify-content: center;
    }
    .cand-card .avatar { width: 52px; height: 52px; font-size: 1.2rem; }
    .stat-tile { padding: 0.8rem; }
    .stat-tile .stat-icon { width: 36px; height: 36px; font-size: 1.1rem; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
}
</style>
"""


def inject_css() -> None:
    """Aplica o CSS global. Chamar uma vez por página, logo após `st.set_page_config`."""
    st.markdown(_CSS, unsafe_allow_html=True)


def brand_bar() -> None:
    """Faixa fina azul+laranja no topo da página (identidade visual sutil)."""
    st.markdown('<div class="brand-bar"></div>', unsafe_allow_html=True)


def hero(titulo: str, subtitulo: str) -> None:
    """Renderiza um hero card no padrão UNIÃO."""
    st.markdown(
        f"""
<div class="hero-card">
    <span class="accent-bar"></span>
    <h1>{titulo}</h1>
    <p class="tagline">{subtitulo}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def action_card(icon: str, title: str, desc: str) -> None:
    """Renderiza um card de ação. Use como placeholder visual; o link/botão fica próximo."""
    st.markdown(
        f"""
<div class="action-card">
    <span class="icon">{icon}</span>
    <div class="title">{title}</div>
    <div class="desc">{desc}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def candidate_header(detalhe: dict) -> None:
    """Card de cabeçalho do candidato — avatar com iniciais + meta + KPIs."""
    nome = detalhe.get("nome_urna") or detalhe.get("nome", "?")
    iniciais = "".join(p[0] for p in nome.split()[:2]).upper()
    cargo = detalhe.get("cargo", "—")
    ano = detalhe.get("ano", "—")
    partido = detalhe.get("partido_sigla") or "—"
    situacao = detalhe.get("situacao") or "—"
    total = detalhe.get("total_votos", 0)
    st.markdown(
        f"""
<div class="cand-card">
    <div class="avatar">{iniciais}</div>
    <div class="info">
        <div class="nome">{nome}</div>
        <div class="meta">{cargo} · {ano} · {partido} · {situacao}</div>
    </div>
    <div class="stats">
        <div class="stat">
            <div class="stat-label">Votos totais</div>
            <div class="stat-value">{total:,}</div>
        </div>
    </div>
</div>
""".replace(",", "."),
        unsafe_allow_html=True,
    )


def empty_state(icon: str, title: str, hint: str = "") -> None:
    """Estado vazio amigável com ícone + título + dica."""
    st.markdown(
        f"""
<div class="empty-state">
    <span class="icon">{icon}</span>
    <div class="title">{title}</div>
    <div class="hint">{hint}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def stat_tile(icon: str, label: str, value: str, delta: str = "", variant: str = "") -> None:
    """KPI compacto com ícone à esquerda. Variant: '', 'accent', 'success', 'warning'."""
    cls = f"stat-tile {variant}" if variant else "stat-tile"
    delta_html = f'<div class="stat-tile-delta">{delta}</div>' if delta else ""
    st.markdown(
        f"""
<div class="{cls}">
    <div class="stat-icon">{icon}</div>
    <div class="stat-body">
        <div class="stat-tile-label">{label}</div>
        <div class="stat-tile-value">{value}</div>
        {delta_html}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def require_login() -> None:
    """Bloqueia a página se o usuário não estiver autenticado.
    Mostra empty state com instrução e chama st.stop().
    """
    from dashboard.api_client import autenticado
    if not autenticado():
        empty_state(
            "🔐", "Acesso restrito",
            "Volte à página inicial e entre com seu e-mail e senha para continuar.",
        )
        st.stop()


def situacao_emoji(situacao: str | None) -> str:
    """Mapeia situação eleitoral para emoji visual."""
    if not situacao:
        return "—"
    s = situacao.upper()
    if s.startswith("ELEIT"):
        return "🟢 Eleito"
    if "SUPLENTE" in s:
        return "🟡 Suplente"
    if "NÃO ELEITO" in s or "NAO ELEITO" in s:
        return "⚪ Não eleito"
    if "RENUNCI" in s or "INDEFER" in s or "CASSAD" in s:
        return "🔴 " + situacao.title()
    return situacao
