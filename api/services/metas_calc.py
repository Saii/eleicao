"""
Lógica de cálculo do módulo Metas.

- Distribuição da meta-mãe entre municípios (ponderado por capilaridade UNIÃO + voto histórico)
- Projeção de votos a partir de apoiadores + base histórica + canais residuais
- Cenários what-if
- Monte Carlo de probabilidade
- Backtest contra eleição passada
- Otimização linear de alocação de recursos (LP simples sem dependências externas)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date


@dataclass
class CenarioProjecao:
    nome: str
    m_nivel_1: float
    m_nivel_2: float
    m_nivel_3: float
    m_nivel_4: float
    fator_evento: float
    decay_temporal: float
    retencao_historica: float


# ---------- Distribuição da meta-mãe ----------

def distribuir_meta_estadual(
    meta_total: int,
    municipios: list[dict],
) -> list[dict]:
    """
    Distribui a meta-mãe pelos municípios usando peso composto:
      - 50% peso eleitoral (aproximado por filiados UNIÃO se disponível, senão votos histórico Rueda)
      - 30% capilaridade UNIÃO 2024 (votos UNIÃO no município)
      - 20% baseline igualitário

    Cada `municipio` deve ter:
      cod_ibge, nome, votos_uniao_2024 (int), filiados_uniao (int), votos_rueda_2022 (int)

    Retorna lista enriquecida com 'votos_alvo' calculado.
    """
    if not municipios:
        return []
    n = len(municipios)

    peso_filiados = sum(m.get("filiados_uniao", 0) for m in municipios)
    peso_uniao = sum(m.get("votos_uniao_2024", 0) for m in municipios)
    peso_rueda = sum(m.get("votos_rueda_2022", 0) for m in municipios)

    out = []
    soma_alvo = 0
    for m in municipios:
        # Componente 1: filiados (50%) — preferir filiados, fallback Rueda histórico
        if peso_filiados > 0:
            c1 = m.get("filiados_uniao", 0) / peso_filiados
        elif peso_rueda > 0:
            c1 = m.get("votos_rueda_2022", 0) / peso_rueda
        else:
            c1 = 1.0 / n

        # Componente 2: capilaridade UNIÃO 2024 (30%)
        c2 = (m.get("votos_uniao_2024", 0) / peso_uniao) if peso_uniao > 0 else 1.0 / n

        # Componente 3: baseline igualitário (20%)
        c3 = 1.0 / n

        peso = 0.5 * c1 + 0.3 * c2 + 0.2 * c3
        alvo = round(meta_total * peso)
        soma_alvo += alvo
        out.append({
            **m,
            "peso_distribuicao": round(peso * 100, 2),
            "votos_alvo": alvo,
        })

    # Ajuste de arredondamento na maior cidade
    diff = meta_total - soma_alvo
    if diff != 0 and out:
        out_sorted = sorted(out, key=lambda x: -x["votos_alvo"])
        out_sorted[0]["votos_alvo"] += diff

    return out


# ---------- Projeção de votos ----------

def projetar_votos_municipio(
    apoiadores_por_nivel: dict[int, int],
    publico_eventos: int,
    voto_historico: int,
    cenario: CenarioProjecao,
) -> dict:
    """
    Projeta votos para um município dado:
      - apoiadores_por_nivel: {1: 10, 2: 5, ...} (nível → contagem)
      - publico_eventos: soma de público estimado em eventos planejados
      - voto_historico: votos do candidato no município em ano anterior

    Retorna breakdown:
      { 'organico', 'eventos', 'historico', 'total' }
    """
    organico = (
        apoiadores_por_nivel.get(1, 0) * cenario.m_nivel_1
        + apoiadores_por_nivel.get(2, 0) * cenario.m_nivel_2
        + apoiadores_por_nivel.get(3, 0) * cenario.m_nivel_3
        + apoiadores_por_nivel.get(4, 0) * cenario.m_nivel_4
    ) * cenario.decay_temporal

    eventos = publico_eventos * cenario.fator_evento * cenario.decay_temporal

    historico = voto_historico * cenario.retencao_historica

    total = organico + eventos + historico

    return {
        "organico": round(organico),
        "eventos": round(eventos),
        "historico": round(historico),
        "total": round(total),
    }


# ---------- Recomendações por regras ----------

def recomendacoes(
    pct_atingido: float,
    pct_tempo_decorrido: float,
    municipios_sem_apoiador: list[dict],
    secoes_gap_sem_apoiador: int,
    eventos_alto_potencial: list[dict],
) -> list[dict]:
    """Gera bullets de recomendação. Cada item: {nivel, texto}."""
    rec = []

    if pct_atingido < pct_tempo_decorrido - 10:
        rec.append({
            "nivel": "alerta",
            "texto": (
                f"⚠️ Velocidade insuficiente: {pct_atingido:.1f}% atingido com "
                f"{pct_tempo_decorrido:.1f}% do tempo decorrido. Acelere captação de apoiadores nos próximos meses."
            ),
        })
    elif pct_atingido > pct_tempo_decorrido + 10:
        rec.append({
            "nivel": "sucesso",
            "texto": (
                f"✅ À frente do cronograma: {pct_atingido:.1f}% atingido com "
                f"{pct_tempo_decorrido:.1f}% do tempo. Mantenha o ritmo."
            ),
        })

    if municipios_sem_apoiador:
        top3 = municipios_sem_apoiador[:3]
        nomes = ", ".join(
            f"**{m['nome']}** ({m['votos_alvo']} votos)" for m in top3
        )
        rec.append({
            "nivel": "info",
            "texto": (
                f"🎯 Sem presença: {len(municipios_sem_apoiador)} municípios com meta "
                f"sem apoiador cadastrado. Prioridade: {nomes}."
            ),
        })

    if secoes_gap_sem_apoiador > 50:
        rec.append({
            "nivel": "info",
            "texto": (
                f"📍 {secoes_gap_sem_apoiador} seções de gap UNIÃO 2024 ainda sem apoiador "
                "do Rueda. Use a aba Estratégia da página Rueda para mapear lideranças locais."
            ),
        })

    if eventos_alto_potencial:
        e = eventos_alto_potencial[0]
        rec.append({
            "nivel": "info",
            "texto": (
                f"📅 Próximo evento de alto retorno: **{e.get('titulo', '?')}** "
                f"em {e.get('local', '?')} (público estimado: {e.get('publico_estimado', 0)})."
            ),
        })

    return rec


# ---------- Monte Carlo ----------

def simular_monte_carlo(
    base_projecao: int,
    meta: int,
    n_simulacoes: int = 5000,
    sigma_relativa: float = 0.20,
) -> dict:
    """
    Simula a distribuição de votos finais com ruído Gaussiano em torno da projeção.
    Retorna probabilidade de bater a meta + percentis P10/P50/P90.
    """
    if base_projecao <= 0:
        return {"prob_atingir": 0.0, "p10": 0, "p50": 0, "p90": 0, "n": n_simulacoes}

    rng = random.Random(42)
    sigma = base_projecao * sigma_relativa
    amostras = sorted(rng.gauss(base_projecao, sigma) for _ in range(n_simulacoes))
    p10 = amostras[int(n_simulacoes * 0.10)]
    p50 = amostras[int(n_simulacoes * 0.50)]
    p90 = amostras[int(n_simulacoes * 0.90)]
    n_atinge = sum(1 for v in amostras if v >= meta)
    prob = n_atinge / n_simulacoes
    return {
        "prob_atingir": round(prob, 3),
        "p10": int(round(p10)),
        "p50": int(round(p50)),
        "p90": int(round(p90)),
        "n": n_simulacoes,
    }


# ---------- Backtest 2022 ----------

def backtest_eleicao_anterior(
    voto_real: int,
    apoiadores_hipoteticos: dict[int, int],
    cenario: CenarioProjecao,
) -> dict:
    """
    Aplica o modelo retroativamente. Como não temos snapshot de apoiadores em 2022,
    assume que apoiadores_hipoteticos eram a base na época. Útil para calibrar.
    """
    proj = projetar_votos_municipio(
        apoiadores_hipoteticos,
        publico_eventos=0,
        voto_historico=0,  # 2022 era a primeira do Rueda — sem histórico anterior
        cenario=cenario,
    )
    erro_abs = abs(proj["total"] - voto_real)
    erro_pct = (erro_abs / voto_real * 100) if voto_real else 0
    return {
        "previsto": proj["total"],
        "real": voto_real,
        "erro_abs": erro_abs,
        "erro_pct": round(erro_pct, 1),
    }


# ---------- Otimização de alocação (LP greedy simples) ----------

def alocar_recursos(
    municipios: list[dict],
    apoiadores_disponiveis: int,
    nivel_apoiador: int = 2,
    cenario: CenarioProjecao | None = None,
) -> list[dict]:
    """
    Aloca apoiadores adicionais entre municípios maximizando votos esperados
    sob restrição: meta_alvo do município (não sobrealocar).

    Estratégia greedy: ordena por gap × multiplicador, distribui até esgotar.
    """
    if cenario is None:
        cenario = CenarioProjecao(
            "default", 0.5, 1.5, 5.0, 30.0, 0.20, 0.65, 0.85,
        )
    mult = {1: cenario.m_nivel_1, 2: cenario.m_nivel_2,
            3: cenario.m_nivel_3, 4: cenario.m_nivel_4}[nivel_apoiador]

    # Ordena municípios pelo gap (alvo - projetado_atual) descendente
    ordenados = sorted(
        municipios,
        key=lambda m: -(m.get("votos_alvo", 0) - m.get("votos_projetados", 0)),
    )

    restante = apoiadores_disponiveis
    out = []
    for m in ordenados:
        gap = max(0, m.get("votos_alvo", 0) - m.get("votos_projetados", 0))
        if gap == 0 or restante <= 0:
            out.append({**m, "alocacao_apoiadores": 0, "votos_adicionais": 0})
            continue
        # Quantos apoiadores são necessários para fechar este gap?
        necessarios = int(round(gap / (mult * cenario.decay_temporal)))
        alocar = min(necessarios, restante)
        votos_add = round(alocar * mult * cenario.decay_temporal)
        restante -= alocar
        out.append({**m, "alocacao_apoiadores": alocar, "votos_adicionais": votos_add})

    return out


# ---------- Tempo decorrido ----------

def pct_tempo_decorrido(data_inicio: date, data_eleicao: date, hoje: date) -> float:
    if hoje >= data_eleicao:
        return 100.0
    if hoje <= data_inicio:
        return 0.0
    total = (data_eleicao - data_inicio).days
    decorrido = (hoje - data_inicio).days
    return round(decorrido / total * 100, 2) if total > 0 else 0.0
