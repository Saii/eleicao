"""
Análise partidária para uma candidatura de referência.
Calcula:
- Coeficiente eleitoral e cadeiras
- Coeficiente partidário, cadeiras pelo QP
- Coligações/federações
- Distribuição regional do voto por partido
- Adversários diretos do candidato
- Disputa pela cadeira (mínimo individual + sobras)
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.security import usuario_atual

router = APIRouter(prefix="", tags=["analise-partidaria"],
                   dependencies=[Depends(usuario_atual)])


# Cadeiras na Câmara dos Deputados por UF
CADEIRAS_DEP_FEDERAL_UF = {
    "AC": 8, "AL": 9, "AM": 8, "AP": 8, "BA": 39, "CE": 22, "DF": 8,
    "ES": 10, "GO": 17, "MA": 18, "MG": 53, "MS": 8, "MT": 8, "PA": 17,
    "PB": 12, "PE": 25, "PI": 10, "PR": 30, "RJ": 46, "RN": 8, "RO": 8,
    "RR": 8, "RS": 31, "SC": 16, "SE": 8, "SP": 70, "TO": 8,
}

# Cadeiras na Assembleia Legislativa do AC
CADEIRAS_DEP_ESTADUAL_AC = 24


def _cadeiras(cargo: str, uf: str = "AC") -> int:
    cargo_l = cargo.lower()
    if "federal" in cargo_l:
        return CADEIRAS_DEP_FEDERAL_UF.get(uf, 8)
    if "estadual" in cargo_l:
        return CADEIRAS_DEP_ESTADUAL_AC
    return 1  # majoritário


@router.get("/candidatos/{candidatura_id}/analise-partidaria")
def analise_partidaria(
    candidatura_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    # 1. Contexto do candidato de referência
    cand = db.execute(text("""
        SELECT cd.id, cd.ano, cd.cargo, cd.numero, cd.partido_numero,
               cd.coligacao, cd.total_votos, cd.situacao,
               c.nome, c.nome_urna, c.id AS candidato_id,
               p.sigla AS partido_sigla, p.nome AS partido_nome
        FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE cd.id = :id
    """), {"id": str(candidatura_id)}).mappings().first()
    if not cand:
        raise HTTPException(404, "Candidatura não encontrada")
    cand = dict(cand)

    cargo = cand["cargo"]
    ano = cand["ano"]
    cadeiras = _cadeiras(cargo)

    # 2. Total de votos válidos no cargo/ano (apenas nominais — legenda não está em votacao)
    votos_validos = db.execute(text("""
        SELECT COALESCE(SUM(votos), 0)
        FROM votacao v
        JOIN candidatura cd ON cd.id = v.candidatura_id
        WHERE cd.ano = :ano AND cd.cargo = :cargo
    """), {"ano": ano, "cargo": cargo}).scalar() or 0
    votos_validos = int(votos_validos)

    coef_eleitoral = round(votos_validos / cadeiras) if cadeiras else 0
    minimo_individual = round(coef_eleitoral * 0.10)

    # 3. Ranking de partidos (votos somados de todos os candidatos do cargo/ano)
    partidos_rows = db.execute(text("""
        SELECT cd.partido_numero, p.sigla, p.nome,
               cd.coligacao,
               COALESCE(SUM(cd.total_votos), 0) AS votos_total,
               COUNT(DISTINCT cd.id) AS qt_candidatos,
               COUNT(DISTINCT CASE WHEN cd.situacao ILIKE 'ELEIT%' THEN cd.id END) AS qt_eleitos
        FROM candidatura cd
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE cd.ano = :ano AND cd.cargo = :cargo
        GROUP BY cd.partido_numero, p.sigla, p.nome, cd.coligacao
        ORDER BY votos_total DESC
    """), {"ano": ano, "cargo": cargo}).mappings().all()

    partidos = []
    for r in partidos_rows:
        coef_part = round(r["votos_total"] / coef_eleitoral, 3) if coef_eleitoral else 0
        cadeiras_qp = int(coef_part)
        atinge_clausula = cadeiras_qp >= 1
        partidos.append({
            "partido_numero": r["partido_numero"],
            "sigla": r["sigla"] or "—",
            "nome": r["nome"] or "—",
            "coligacao": r["coligacao"],
            "votos_total": int(r["votos_total"]),
            "qt_candidatos": r["qt_candidatos"],
            "qt_eleitos": r["qt_eleitos"],
            "coef_partidario": coef_part,
            "cadeiras_qp": cadeiras_qp,
            "atinge_clausula": atinge_clausula,
            "pct_validos": round(r["votos_total"] / votos_validos * 100, 2) if votos_validos else 0,
        })

    # 4. Federações/coligações (agrupado por coligacao)
    federacoes_rows = db.execute(text("""
        SELECT cd.coligacao,
               COALESCE(SUM(cd.total_votos), 0) AS votos_total,
               STRING_AGG(DISTINCT p.sigla, ' / ') AS partidos_siglas,
               COUNT(DISTINCT cd.id) AS qt_candidatos,
               COUNT(DISTINCT CASE WHEN cd.situacao ILIKE 'ELEIT%' THEN cd.id END) AS qt_eleitos
        FROM candidatura cd
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE cd.ano = :ano AND cd.cargo = :cargo AND cd.coligacao IS NOT NULL
        GROUP BY cd.coligacao
        ORDER BY votos_total DESC
    """), {"ano": ano, "cargo": cargo}).mappings().all()

    federacoes = []
    for r in federacoes_rows:
        coef_fed = round(r["votos_total"] / coef_eleitoral, 3) if coef_eleitoral else 0
        federacoes.append({
            "coligacao": r["coligacao"],
            "partidos_siglas": r["partidos_siglas"],
            "votos_total": int(r["votos_total"]),
            "qt_candidatos": r["qt_candidatos"],
            "qt_eleitos": r["qt_eleitos"],
            "coef_partidario": coef_fed,
            "cadeiras_qp": int(coef_fed),
        })

    # 5. Distribuição regional (votos por partido x município)
    regional_rows = db.execute(text("""
        SELECT v.municipio_cod, m.nome AS municipio_nome,
               cd.partido_numero, p.sigla,
               SUM(v.votos) AS votos
        FROM votacao v
        JOIN candidatura cd ON cd.id = v.candidatura_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        LEFT JOIN municipio m ON m.cod_ibge = v.municipio_cod
        WHERE cd.ano = :ano AND cd.cargo = :cargo
        GROUP BY v.municipio_cod, m.nome, cd.partido_numero, p.sigla
    """), {"ano": ano, "cargo": cargo}).mappings().all()

    # Partido dominante por município
    dominante_por_mun: dict[int, dict] = {}
    for r in regional_rows:
        mc = r["municipio_cod"]
        if not mc:
            continue
        cur = dominante_por_mun.get(mc)
        if not cur or r["votos"] > cur["votos"]:
            dominante_por_mun[mc] = {
                "municipio_cod": mc,
                "municipio_nome": r["municipio_nome"],
                "partido_dominante": r["sigla"],
                "votos": int(r["votos"]),
            }

    # 6. Adversários diretos (top 30 candidatos próximos em votos do Rueda)
    adversarios_rows = db.execute(text("""
        WITH ranked AS (
            SELECT cd.id AS candidatura_id, c.nome, c.nome_urna,
                   p.sigla AS partido, cd.coligacao, cd.numero,
                   cd.total_votos, cd.situacao,
                   ABS(cd.total_votos - :ref_votos) AS distancia,
                   RANK() OVER (ORDER BY cd.total_votos DESC) AS posicao
            FROM candidatura cd
            JOIN candidato c ON c.id = cd.candidato_id
            LEFT JOIN partido p ON p.numero = cd.partido_numero
            WHERE cd.ano = :ano AND cd.cargo = :cargo
        )
        SELECT * FROM ranked
        ORDER BY distancia ASC
        LIMIT 15
    """), {"ano": ano, "cargo": cargo, "ref_votos": cand["total_votos"]}).mappings().all()
    adversarios = [dict(r) for r in adversarios_rows]

    # 7. Co-partidários (mesmo partido na mesma eleição)
    internos_rows = db.execute(text("""
        SELECT cd.id AS candidatura_id, c.nome, c.nome_urna,
               cd.numero, cd.total_votos, cd.situacao,
               RANK() OVER (PARTITION BY cd.partido_numero ORDER BY cd.total_votos DESC) AS rank_partido
        FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        WHERE cd.ano = :ano AND cd.cargo = :cargo AND cd.partido_numero = :pn
        ORDER BY cd.total_votos DESC
    """), {"ano": ano, "cargo": cargo, "pn": cand["partido_numero"]}).mappings().all()
    internos = [dict(r) for r in internos_rows]
    rueda_rank_partido = next(
        (i["rank_partido"] for i in internos if str(i["candidatura_id"]) == str(candidatura_id)),
        None,
    )

    # 8. Disputa pela cadeira
    posicao_geral = next((a["posicao"] for a in adversarios
                          if str(a["candidatura_id"]) == str(candidatura_id)), None)
    if posicao_geral is None:
        posicao_geral = db.execute(text("""
            WITH r AS (
                SELECT id, RANK() OVER (ORDER BY total_votos DESC) AS pos
                FROM candidatura WHERE ano = :ano AND cargo = :cargo
            )
            SELECT pos FROM r WHERE id = :id
        """), {"ano": ano, "cargo": cargo, "id": str(candidatura_id)}).scalar()

    ultimo_eleito_votos = db.execute(text("""
        SELECT MIN(total_votos) FROM candidatura
        WHERE ano = :ano AND cargo = :cargo AND situacao ILIKE 'ELEIT%'
    """), {"ano": ano, "cargo": cargo}).scalar() or 0

    primeiro_suplente_votos = db.execute(text("""
        SELECT MAX(total_votos) FROM candidatura
        WHERE ano = :ano AND cargo = :cargo AND total_votos < :ult
          AND id != :id
    """), {"ano": ano, "cargo": cargo, "ult": int(ultimo_eleito_votos),
           "id": str(candidatura_id)}).scalar() or 0

    delta_minimo = minimo_individual - cand["total_votos"]
    delta_ultimo_eleito = int(ultimo_eleito_votos) - cand["total_votos"]
    atinge_minimo = cand["total_votos"] >= minimo_individual

    # 9. Comparativo com 2024 (contexto de tendência do partido)
    if ano == 2022:
        evol_partido = db.execute(text("""
            SELECT cd.ano, COALESCE(SUM(cd.total_votos), 0) AS total
            FROM candidatura cd
            WHERE cd.partido_numero = :pn AND cd.ano IN (2022, 2024)
            GROUP BY cd.ano ORDER BY cd.ano
        """), {"pn": cand["partido_numero"]}).mappings().all()
        evolucao_partido = [dict(e) for e in evol_partido]
    else:
        evolucao_partido = []

    return {
        "contexto": {
            "candidatura_id": str(candidatura_id),
            "candidato_nome": cand["nome"],
            "candidato_urna": cand["nome_urna"],
            "ano": ano,
            "cargo": cargo,
            "numero": cand["numero"],
            "partido_sigla": cand["partido_sigla"],
            "coligacao": cand["coligacao"],
            "votos_candidato": cand["total_votos"],
            "situacao": cand["situacao"],
            "cadeiras_disputadas": cadeiras,
            "votos_validos_total": votos_validos,
            "coeficiente_eleitoral": coef_eleitoral,
            "minimo_individual": minimo_individual,
        },
        "partidos": partidos,
        "federacoes": federacoes,
        "regional": list(dominante_por_mun.values()),
        "adversarios": adversarios,
        "internos_partido": internos,
        "rueda_rank_partido": rueda_rank_partido,
        "disputa_cadeira": {
            "posicao_geral": int(posicao_geral) if posicao_geral else None,
            "votos_candidato": cand["total_votos"],
            "minimo_individual": minimo_individual,
            "atinge_minimo": atinge_minimo,
            "delta_minimo": delta_minimo,
            "ultimo_eleito_votos": int(ultimo_eleito_votos),
            "delta_ultimo_eleito": delta_ultimo_eleito,
            "primeiro_suplente_votos": int(primeiro_suplente_votos),
        },
        "evolucao_partido_2022_2024": evolucao_partido,
    }
