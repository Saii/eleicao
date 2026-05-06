from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.security import usuario_atual
from api.services.metas_calc import (
    CenarioProjecao,
    alocar_recursos,
    backtest_eleicao_anterior,
    distribuir_meta_estadual,
    pct_tempo_decorrido,
    projetar_votos_municipio,
    recomendacoes,
    simular_monte_carlo,
)

router = APIRouter(prefix="/metas-avancado", tags=["metas-avancado"],
                   dependencies=[Depends(usuario_atual)])

DATA_ELEICAO_2026 = date(2026, 10, 4)


def _cenario_ativo(db: Session, nome: str | None = None) -> CenarioProjecao:
    if nome:
        row = db.execute(text("SELECT * FROM projecao_config WHERE nome = :n"),
                         {"n": nome}).mappings().first()
    else:
        row = db.execute(text("SELECT * FROM projecao_config WHERE ativo = TRUE LIMIT 1")).mappings().first()
    if not row:
        row = db.execute(text("SELECT * FROM projecao_config WHERE nome = 'realista'")).mappings().first()
    if not row:
        raise HTTPException(500, "Nenhuma configuração de projeção encontrada")
    return CenarioProjecao(
        nome=row["nome"],
        m_nivel_1=float(row["m_nivel_1"]),
        m_nivel_2=float(row["m_nivel_2"]),
        m_nivel_3=float(row["m_nivel_3"]),
        m_nivel_4=float(row["m_nivel_4"]),
        fator_evento=float(row["fator_evento"]),
        decay_temporal=float(row["decay_temporal"]),
        retencao_historica=float(row["retencao_historica"]),
    )


def _dados_municipios(db: Session, candidatura_id: UUID | None = None) -> list[dict]:
    """Carrega métricas por município: filiados UNIÃO, votos UNIÃO 2024, votos histórico do candidato."""
    cand_clause = ""
    params = {}
    if candidatura_id:
        cand_clause = "WHERE id = :cid"
        params["cid"] = str(candidatura_id)
    rows = db.execute(text(f"""
        SELECT m.cod_ibge, m.nome,
            COALESCE(fil.qt, 0) AS filiados_uniao,
            COALESCE(uniao.votos, 0) AS votos_uniao_2024,
            COALESCE(hist.votos, 0) AS votos_rueda_2022
        FROM municipio m
        LEFT JOIN (
            SELECT municipio_cod, SUM(qt_filiado) AS qt
            FROM filiacao_perfil fp
            JOIN partido p ON p.numero = fp.partido_numero
            WHERE p.sigla = 'UNIÃO'
            GROUP BY municipio_cod
        ) fil ON fil.municipio_cod = m.cod_ibge
        LEFT JOIN (
            SELECT v.municipio_cod, SUM(v.votos) AS votos
            FROM votacao v
            JOIN candidatura cd ON cd.id = v.candidatura_id
            JOIN partido p ON p.numero = cd.partido_numero
            WHERE cd.ano = 2024 AND p.sigla = 'UNIÃO'
            GROUP BY v.municipio_cod
        ) uniao ON uniao.municipio_cod = m.cod_ibge
        LEFT JOIN (
            SELECT v.municipio_cod, SUM(v.votos) AS votos
            FROM votacao v
            JOIN candidato c ON c.id = (SELECT candidato_id FROM candidatura WHERE id = v.candidatura_id)
            JOIN candidatura cd ON cd.id = v.candidatura_id
            WHERE c.nome_normalizado ILIKE '%rueda%' AND cd.ano = 2022
            GROUP BY v.municipio_cod
        ) hist ON hist.municipio_cod = m.cod_ibge
        ORDER BY m.nome
    """), params).mappings().all()
    return [dict(r) for r in rows]


@router.post("/setup-meta-mae")
def setup_meta_mae(
    votos_alvo: int = 40000,
    cargo: str = "Deputado Federal",
    ano_alvo: int = 2026,
    candidatura_referencia: str = "rueda",
    db: Session = Depends(get_db),
    user: dict = Depends(usuario_atual),
) -> dict:
    """Cria/atualiza a meta-mãe de 40k votos e distribui pelos 22 municípios."""

    # Encontra candidatura de referência (Rueda 2022) para histórico
    cid_ref_row = db.execute(text("""
        SELECT cd.id FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        WHERE c.nome_normalizado ILIKE :q AND cd.cargo ILIKE :cargo
        ORDER BY cd.ano DESC LIMIT 1
    """), {"q": f"%{candidatura_referencia}%", "cargo": f"%{cargo}%"}).first()
    cid_ref = str(cid_ref_row[0]) if cid_ref_row else None

    # Apaga meta-mãe e filhas anteriores (idempotente)
    db.execute(text("""
        DELETE FROM meta WHERE tipo = 'estado'
           OR meta_pai_id IN (SELECT id FROM meta WHERE tipo = 'estado')
    """))

    # Cria meta-mãe
    mae = db.execute(text("""
        INSERT INTO meta (descricao, votos_alvo, tipo, cargo, ano_alvo, data_eleicao,
                          candidatura_id, responsavel, status)
        VALUES (:d, :v, 'estado', :c, :a, :de, :cr, :r, 'em_andamento')
        RETURNING id
    """), {
        "d": f"Meta {votos_alvo} votos · {cargo} {ano_alvo} · Estado do Acre",
        "v": votos_alvo, "c": cargo, "a": ano_alvo,
        "de": DATA_ELEICAO_2026,
        "cr": cid_ref, "r": user["id"],
    }).scalar()

    # Distribui pelos municípios
    municipios = _dados_municipios(db)
    distribuicao = distribuir_meta_estadual(votos_alvo, municipios)

    for m in distribuicao:
        db.execute(text("""
            INSERT INTO meta (descricao, municipio_cod, votos_alvo, tipo, cargo, ano_alvo,
                              data_eleicao, candidatura_id, meta_pai_id, responsavel, status)
            VALUES (:d, :mc, :v, 'municipio', :c, :a, :de, :cr, :pai, :r, 'em_andamento')
        """), {
            "d": f"Meta {m['votos_alvo']} votos em {m['nome']}",
            "mc": m["cod_ibge"], "v": m["votos_alvo"],
            "c": cargo, "a": ano_alvo, "de": DATA_ELEICAO_2026,
            "cr": cid_ref, "pai": str(mae), "r": user["id"],
        })
    db.commit()

    return {
        "meta_mae_id": str(mae),
        "meta_total": votos_alvo,
        "distribuicao": distribuicao,
        "candidatura_referencia": cid_ref,
    }


@router.get("/dashboard")
def metas_dashboard(
    cenario: str = "realista",
    db: Session = Depends(get_db),
) -> dict:
    """Resumo executivo da meta-mãe + decomposição por município com projeção."""
    cen = _cenario_ativo(db, cenario)

    mae = db.execute(text("""
        SELECT id, votos_alvo, cargo, ano_alvo, data_eleicao, candidatura_id, criado_em
        FROM meta WHERE tipo = 'estado' ORDER BY criado_em DESC LIMIT 1
    """)).mappings().first()
    if not mae:
        raise HTTPException(404, "Meta-mãe não configurada — chame POST /metas-avancado/setup-meta-mae")
    mae = dict(mae)

    # Filhas (municípios)
    filhas = db.execute(text("""
        SELECT m.id, m.municipio_cod, mu.nome AS municipio_nome, m.votos_alvo
        FROM meta m
        LEFT JOIN municipio mu ON mu.cod_ibge = m.municipio_cod
        WHERE m.meta_pai_id = :pai
        ORDER BY m.votos_alvo DESC
    """), {"pai": str(mae["id"])}).mappings().all()
    filhas = [dict(r) for r in filhas]

    # Apoiadores agregados por município e nível
    apoia_rows = db.execute(text("""
        SELECT municipio_cod, nivel_engajamento, COUNT(*) AS qt
        FROM apoiador
        WHERE municipio_cod IS NOT NULL
        GROUP BY municipio_cod, nivel_engajamento
    """)).mappings().all()
    apoia_map: dict[int, dict[int, int]] = {}
    for r in apoia_rows:
        d = apoia_map.setdefault(r["municipio_cod"], {})
        d[r["nivel_engajamento"] or 1] = r["qt"]

    # Eventos futuros
    eventos_rows = db.execute(text("""
        SELECT municipio_cod, COALESCE(SUM(publico_estimado), 0) AS publico
        FROM evento
        WHERE inicio > NOW() AND status NOT IN ('cancelado', 'realizado')
        GROUP BY municipio_cod
    """)).mappings().all()
    publico_map = {r["municipio_cod"]: r["publico"] for r in eventos_rows}

    # Histórico Rueda
    hist_map: dict[int, int] = {}
    if mae["candidatura_id"]:
        hist_rows = db.execute(text("""
            SELECT municipio_cod, SUM(votos) AS v FROM votacao
            WHERE candidatura_id = :id AND municipio_cod IS NOT NULL
            GROUP BY municipio_cod
        """), {"id": str(mae["candidatura_id"])}).mappings().all()
        hist_map = {r["municipio_cod"]: r["v"] for r in hist_rows}

    # Projeta
    total_proj = 0
    total_apoia = 0
    sem_apoiador: list[dict] = []
    for f in filhas:
        mc = f["municipio_cod"]
        ap = apoia_map.get(mc, {})
        publico = int(publico_map.get(mc, 0))
        hist = int(hist_map.get(mc, 0))
        proj = projetar_votos_municipio(ap, publico, hist, cen)
        f["projecao"] = proj
        f["votos_projetados"] = proj["total"]
        f["apoiadores"] = sum(ap.values())
        f["pct"] = round(proj["total"] / f["votos_alvo"] * 100, 1) if f["votos_alvo"] else 0
        total_proj += proj["total"]
        total_apoia += f["apoiadores"]
        if f["apoiadores"] == 0 and f["votos_alvo"] > 0:
            sem_apoiador.append({"nome": f["municipio_nome"], "votos_alvo": f["votos_alvo"]})

    pct_meta = round(total_proj / mae["votos_alvo"] * 100, 1) if mae["votos_alvo"] else 0
    inicio = mae["criado_em"].date() if mae.get("criado_em") else date.today()
    pct_tempo = pct_tempo_decorrido(inicio, mae["data_eleicao"], date.today())

    secoes_gap_sem_ap = 0
    if mae["candidatura_id"]:
        secoes_gap_sem_ap = db.execute(text("""
            SELECT COUNT(DISTINCT se.id)
            FROM secao_eleitoral se
            JOIN votacao_secao vs ON vs.secao_id = se.id
            JOIN candidatura cd ON cd.id = vs.candidatura_id
            JOIN partido p ON p.numero = cd.partido_numero
            WHERE cd.ano = 2024 AND p.sigla = 'UNIÃO'
              AND se.id NOT IN (
                SELECT secao_id FROM votacao_secao WHERE candidatura_id = :rid
              )
        """), {"rid": str(mae["candidatura_id"])}).scalar() or 0

    eventos_alto = db.execute(text("""
        SELECT titulo, local, publico_estimado, inicio
        FROM evento
        WHERE inicio > NOW() AND status NOT IN ('cancelado', 'realizado')
          AND publico_estimado > 100
        ORDER BY inicio LIMIT 5
    """)).mappings().all()

    rec = recomendacoes(
        pct_meta, pct_tempo,
        sorted(sem_apoiador, key=lambda x: -x["votos_alvo"]),
        secoes_gap_sem_ap,
        [dict(e) for e in eventos_alto],
    )

    return {
        "meta_mae": {
            "id": str(mae["id"]),
            "votos_alvo": mae["votos_alvo"],
            "cargo": mae["cargo"],
            "ano_alvo": mae["ano_alvo"],
            "data_eleicao": mae["data_eleicao"].isoformat(),
        },
        "kpis": {
            "votos_projetados": total_proj,
            "apoiadores_total": total_apoia,
            "pct_atingido": pct_meta,
            "pct_tempo_decorrido": pct_tempo,
            "distancia_votos": mae["votos_alvo"] - total_proj,
            "municipios_sem_apoiador": len(sem_apoiador),
            "secoes_gap_sem_apoiador": int(secoes_gap_sem_ap),
        },
        "filhas": filhas,
        "recomendacoes": rec,
        "cenario_usado": cen.nome,
    }


@router.get("/cenarios")
def listar_cenarios(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(text("SELECT * FROM projecao_config ORDER BY nome")).mappings().all()
    return [dict(r) for r in rows]


@router.get("/what-if")
def what_if(
    m_nivel_1: float = 0.5,
    m_nivel_2: float = 1.5,
    m_nivel_3: float = 5.0,
    m_nivel_4: float = 30.0,
    fator_evento: float = 0.20,
    decay_temporal: float = 0.65,
    retencao_historica: float = 0.85,
    db: Session = Depends(get_db),
) -> dict:
    """Recalcula a projeção com parâmetros customizados (sem persistir)."""
    cen = CenarioProjecao(
        "custom", m_nivel_1, m_nivel_2, m_nivel_3, m_nivel_4,
        fator_evento, decay_temporal, retencao_historica,
    )

    mae = db.execute(text("""
        SELECT id, votos_alvo, candidatura_id FROM meta
        WHERE tipo = 'estado' ORDER BY criado_em DESC LIMIT 1
    """)).mappings().first()
    if not mae:
        raise HTTPException(404, "Meta-mãe não configurada")

    apoia_rows = db.execute(text("""
        SELECT municipio_cod, nivel_engajamento, COUNT(*) AS qt
        FROM apoiador WHERE municipio_cod IS NOT NULL
        GROUP BY municipio_cod, nivel_engajamento
    """)).mappings().all()
    apoia_map: dict[int, dict[int, int]] = {}
    for r in apoia_rows:
        apoia_map.setdefault(r["municipio_cod"], {})[r["nivel_engajamento"] or 1] = r["qt"]

    publico_map = dict(db.execute(text("""
        SELECT municipio_cod, COALESCE(SUM(publico_estimado), 0) FROM evento
        WHERE inicio > NOW() AND status NOT IN ('cancelado','realizado')
        GROUP BY municipio_cod
    """)).all())

    hist_map = {}
    if mae["candidatura_id"]:
        hist_map = dict(db.execute(text("""
            SELECT municipio_cod, SUM(votos) FROM votacao
            WHERE candidatura_id = :id AND municipio_cod IS NOT NULL
            GROUP BY municipio_cod
        """), {"id": str(mae["candidatura_id"])}).all())

    total = 0
    for cod in apoia_map.keys() | hist_map.keys():
        ap = apoia_map.get(cod, {})
        proj = projetar_votos_municipio(ap, int(publico_map.get(cod, 0) or 0),
                                         int(hist_map.get(cod, 0) or 0), cen)
        total += proj["total"]

    return {
        "votos_projetados": total,
        "votos_alvo": mae["votos_alvo"],
        "pct_atingido": round(total / mae["votos_alvo"] * 100, 1) if mae["votos_alvo"] else 0,
        "distancia": mae["votos_alvo"] - total,
        "params": cen.__dict__,
    }


@router.post("/snapshot")
def criar_snapshot(
    cenario: str = "realista",
    db: Session = Depends(get_db),
    user: dict = Depends(usuario_atual),
) -> dict:
    """Salva snapshot do estado atual para burndown histórico."""
    dash = metas_dashboard(cenario, db)
    mae_id = dash["meta_mae"]["id"]
    db.execute(text("""
        INSERT INTO meta_snapshot (meta_id, data, votos_projetados, apoiadores_count,
                                    pct_atingido, cenario)
        VALUES (:m, CURRENT_DATE, :v, :a, :p, :c)
        ON CONFLICT (meta_id, data, cenario) DO UPDATE SET
            votos_projetados = EXCLUDED.votos_projetados,
            apoiadores_count = EXCLUDED.apoiadores_count,
            pct_atingido = EXCLUDED.pct_atingido
    """), {
        "m": mae_id,
        "v": dash["kpis"]["votos_projetados"],
        "a": dash["kpis"]["apoiadores_total"],
        "p": dash["kpis"]["pct_atingido"],
        "c": cenario,
    })
    db.commit()
    return {"salvo": True, "data": str(date.today())}


@router.get("/historico")
def historico(
    cenario: str = "realista",
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(text("""
        SELECT s.data, s.votos_projetados, s.apoiadores_count, s.pct_atingido
        FROM meta_snapshot s
        JOIN meta m ON m.id = s.meta_id
        WHERE m.tipo = 'estado' AND s.cenario = :c
        ORDER BY s.data
    """), {"c": cenario}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/monte-carlo")
def monte_carlo(
    cenario: str = "realista",
    sigma: float = 0.20,
    n: int = 5000,
    db: Session = Depends(get_db),
) -> dict:
    dash = metas_dashboard(cenario, db)
    return simular_monte_carlo(
        dash["kpis"]["votos_projetados"],
        dash["meta_mae"]["votos_alvo"],
        n_simulacoes=n, sigma_relativa=sigma,
    )


@router.get("/backtest")
def backtest(
    apoiadores_n1: int = 20, apoiadores_n2: int = 50,
    apoiadores_n3: int = 15, apoiadores_n4: int = 5,
    cenario: str = "realista",
    db: Session = Depends(get_db),
) -> dict:
    cen = _cenario_ativo(db, cenario)
    voto_real = db.execute(text("""
        SELECT cd.total_votos FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        WHERE c.nome_normalizado ILIKE '%rueda%' AND cd.ano = 2022
        LIMIT 1
    """)).scalar() or 0
    return backtest_eleicao_anterior(
        int(voto_real),
        {1: apoiadores_n1, 2: apoiadores_n2, 3: apoiadores_n3, 4: apoiadores_n4},
        cen,
    )


@router.get("/alocar")
def alocar(
    apoiadores_disponiveis: int = 100,
    nivel: int = 2,
    cenario: str = "realista",
    db: Session = Depends(get_db),
) -> list[dict]:
    cen = _cenario_ativo(db, cenario)
    dash = metas_dashboard(cenario, db)
    return alocar_recursos(dash["filhas"], apoiadores_disponiveis, nivel, cen)

