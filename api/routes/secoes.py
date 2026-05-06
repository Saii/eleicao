from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.security import usuario_atual

router = APIRouter(prefix="", tags=["secoes"],
                   dependencies=[Depends(usuario_atual)])


@router.get("/secoes/{zona}/{nr_secao}/top")
def top_na_secao(
    zona: int,
    nr_secao: int,
    cargo: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[dict]:
    sql = """
        SELECT c.nome, c.nome_urna, p.sigla AS partido, cd.cargo, cd.numero,
               vs.votos
        FROM votacao_secao vs
        JOIN candidatura cd ON cd.id = vs.candidatura_id
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        JOIN secao_eleitoral se ON se.id = vs.secao_id
        WHERE se.zona_numero = :z AND se.nr_secao = :s
    """
    params: dict = {"z": zona, "s": nr_secao, "lim": limit}
    if cargo:
        sql += " AND cd.cargo ILIKE :c"; params["c"] = f"%{cargo}%"
    sql += " ORDER BY vs.votos DESC LIMIT :lim"
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/candidatos/{candidatura_id}/secoes")
def votos_por_secao_candidato(
    candidatura_id: UUID,
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(text("""
        SELECT se.zona_numero, se.nr_secao, se.municipio_cod,
               m.nome AS municipio_nome,
               lv.id AS local_id, lv.nome AS local_nome,
               lv.latitude, lv.longitude, vs.votos
        FROM votacao_secao vs
        JOIN secao_eleitoral se ON se.id = vs.secao_id
        LEFT JOIN local_votacao lv ON lv.id = se.local_id
        LEFT JOIN municipio m ON m.cod_ibge = se.municipio_cod
        WHERE vs.candidatura_id = :id
        ORDER BY vs.votos DESC
    """), {"id": str(candidatura_id)}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/secoes/{zona}/{nr_secao}/detalhe-gap")
def detalhe_gap_secao(
    zona: int,
    nr_secao: int,
    candidatura_id: UUID,
    sigla_partido: str = "UNIÃO",
    ano_cruzamento: int = 2024,
    db: Session = Depends(get_db),
) -> dict:
    """Detalhe de uma seção: contexto do candidato (Rueda) + top do partido + top geral."""

    # 1. Info da seção
    sec = db.execute(text("""
        SELECT se.id, se.zona_numero, se.nr_secao, se.municipio_cod,
               m.nome AS municipio_nome,
               lv.id AS local_id, lv.nome AS local_nome,
               lv.endereco, lv.bairro, lv.latitude, lv.longitude
        FROM secao_eleitoral se
        LEFT JOIN municipio m ON m.cod_ibge = se.municipio_cod
        LEFT JOIN local_votacao lv ON lv.id = se.local_id
        WHERE se.zona_numero = :z AND se.nr_secao = :s
    """), {"z": zona, "s": nr_secao}).mappings().first()
    if not sec:
        raise HTTPException(404, "Seção não encontrada")
    sec = dict(sec)

    # 2. Info do candidato de referência (Rueda)
    cand_meta = db.execute(text("""
        SELECT c.nome, c.nome_urna, cd.ano, cd.cargo, cd.numero,
               p.sigla AS partido_sigla, cd.total_votos
        FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE cd.id = :id
    """), {"id": str(candidatura_id)}).mappings().first()
    if not cand_meta:
        raise HTTPException(404, "Candidatura não encontrada")
    cand_meta = dict(cand_meta)

    # Votos do Rueda na seção (vai ser 0 quando é gap)
    votos_secao = db.execute(text("""
        SELECT COALESCE(SUM(vs.votos), 0) FROM votacao_secao vs
        JOIN secao_eleitoral se ON se.id = vs.secao_id
        WHERE vs.candidatura_id = :id AND se.zona_numero = :z AND se.nr_secao = :s
    """), {"id": str(candidatura_id), "z": zona, "s": nr_secao}).scalar() or 0

    # Votos na zona inteira
    votos_zona = db.execute(text("""
        SELECT COALESCE(SUM(vs.votos), 0) FROM votacao_secao vs
        JOIN secao_eleitoral se ON se.id = vs.secao_id
        WHERE vs.candidatura_id = :id AND se.zona_numero = :z
    """), {"id": str(candidatura_id), "z": zona}).scalar() or 0

    # Votos no município
    votos_municipio = db.execute(text("""
        SELECT COALESCE(SUM(vs.votos), 0) FROM votacao_secao vs
        JOIN secao_eleitoral se ON se.id = vs.secao_id
        WHERE vs.candidatura_id = :id AND se.municipio_cod = :m
    """), {"id": str(candidatura_id), "m": sec["municipio_cod"]}).scalar() or 0

    # Ranking do Rueda na zona (entre candidaturas do mesmo ano/cargo)
    ranking_row = db.execute(text("""
        WITH agg AS (
          SELECT vs.candidatura_id, SUM(vs.votos) AS v
          FROM votacao_secao vs
          JOIN secao_eleitoral se ON se.id = vs.secao_id
          JOIN candidatura cd ON cd.id = vs.candidatura_id
          WHERE se.zona_numero = :z AND cd.ano = :ano AND cd.cargo = :cargo
          GROUP BY vs.candidatura_id
        ),
        ranked AS (
          SELECT candidatura_id, v,
                 RANK() OVER (ORDER BY v DESC) AS r,
                 COUNT(*) OVER () AS total
          FROM agg
        )
        SELECT r AS ranking, total FROM ranked WHERE candidatura_id = :id
    """), {"z": zona, "ano": cand_meta["ano"], "cargo": cand_meta["cargo"],
           "id": str(candidatura_id)}).mappings().first()

    # 3. Top do partido na seção (ano cruzamento)
    p_row = db.execute(text("SELECT numero FROM partido WHERE sigla = :s"),
                       {"s": sigla_partido.upper()}).first()
    partido_num = p_row[0] if p_row else None

    top_partido = []
    if partido_num is not None:
        rows = db.execute(text("""
            SELECT c.nome, c.nome_urna, cd.cargo, cd.numero,
                   cd.municipio_cod, m.nome AS municipio_nome,
                   vs.votos, cd.total_votos
            FROM votacao_secao vs
            JOIN secao_eleitoral se ON se.id = vs.secao_id
            JOIN candidatura cd ON cd.id = vs.candidatura_id
            JOIN candidato c ON c.id = cd.candidato_id
            LEFT JOIN municipio m ON m.cod_ibge = cd.municipio_cod
            WHERE se.zona_numero = :z AND se.nr_secao = :s
              AND cd.ano = :ano AND cd.partido_numero = :p
            ORDER BY vs.votos DESC LIMIT 10
        """), {"z": zona, "s": nr_secao, "ano": ano_cruzamento, "p": partido_num}).mappings().all()
        top_partido = [dict(r) for r in rows]

    # 4. Top geral (qualquer partido) na seção
    rows_geral = db.execute(text("""
        SELECT c.nome, c.nome_urna, cd.cargo, cd.numero,
               p.sigla AS partido,
               cd.municipio_cod, m.nome AS municipio_nome,
               vs.votos, cd.total_votos
        FROM votacao_secao vs
        JOIN secao_eleitoral se ON se.id = vs.secao_id
        JOIN candidatura cd ON cd.id = vs.candidatura_id
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        LEFT JOIN municipio m ON m.cod_ibge = cd.municipio_cod
        WHERE se.zona_numero = :z AND se.nr_secao = :s AND cd.ano = :ano
        ORDER BY vs.votos DESC LIMIT 5
    """), {"z": zona, "s": nr_secao, "ano": ano_cruzamento}).mappings().all()
    top_geral = [dict(r) for r in rows_geral]

    return {
        "secao": sec,
        "candidato_ref": {
            **cand_meta,
            "votos_secao": int(votos_secao),
            "votos_zona": int(votos_zona),
            "votos_municipio": int(votos_municipio),
            "ranking_zona": int(ranking_row["ranking"]) if ranking_row else None,
            "total_candidatos_zona": int(ranking_row["total"]) if ranking_row else None,
        },
        "top_partido": top_partido,
        "top_geral": top_geral,
        "params": {"sigla_partido": sigla_partido.upper(), "ano_cruzamento": ano_cruzamento},
    }


@router.get("/candidatos/{candidatura_id}/gap-analysis")
def gap_analysis(
    candidatura_id: UUID,
    ano_cruzamento: int = 2024,
    sigla_partido: str = "UNIÃO",
    top_n: int = 15,
    db: Session = Depends(get_db),
) -> dict:
    """
    Identifica seções onde o candidato (Rueda) teve 0 votos mas o partido teve voto
    em outra eleição (default: UNIÃO 2024). Retorna KPIs, lista de seções, top aliados
    do partido e top líderes locais (qualquer partido) nessas seções, além de
    recomendações geradas por regras.
    """
    p_row = db.execute(
        text("SELECT numero FROM partido WHERE sigla = :s"),
        {"s": sigla_partido.upper()},
    ).first()
    if not p_row:
        raise HTTPException(404, f"Partido {sigla_partido} não encontrado")
    partido_numero = p_row[0]

    # Total de seções com voto da candidatura de referência (Rueda)
    base_total = db.execute(
        text("SELECT COUNT(*) FROM votacao_secao WHERE candidatura_id = :id"),
        {"id": str(candidatura_id)},
    ).scalar() or 0

    # Seções gap = onde Rueda = 0 e partido X teve voto no ano cruzamento
    secoes_gap = db.execute(text("""
        WITH partido_secoes AS (
            SELECT vs.secao_id, SUM(vs.votos) AS v_partido
            FROM votacao_secao vs
            JOIN candidatura cd ON cd.id = vs.candidatura_id
            WHERE cd.ano = :ano AND cd.partido_numero = :p
            GROUP BY vs.secao_id
        ),
        secoes_rueda AS (
            SELECT DISTINCT secao_id FROM votacao_secao WHERE candidatura_id = :rid
        )
        SELECT ps.secao_id, ps.v_partido,
               se.zona_numero, se.nr_secao, se.municipio_cod,
               m.nome AS municipio_nome,
               lv.id AS local_id, lv.nome AS local_nome,
               lv.endereco, lv.bairro, lv.latitude, lv.longitude
        FROM partido_secoes ps
        LEFT JOIN secoes_rueda sr ON sr.secao_id = ps.secao_id
        JOIN secao_eleitoral se ON se.id = ps.secao_id
        LEFT JOIN municipio m ON m.cod_ibge = se.municipio_cod
        LEFT JOIN local_votacao lv ON lv.id = se.local_id
        WHERE sr.secao_id IS NULL
        ORDER BY ps.v_partido DESC
    """), {"ano": ano_cruzamento, "p": partido_numero, "rid": str(candidatura_id)}).mappings().all()
    secoes_gap = [dict(r) for r in secoes_gap]

    if not secoes_gap:
        return {
            "kpis": {"secoes_gap": 0, "votos_partido_perdidos": 0,
                     "secoes_rueda": base_total, "municipios_gap": 0},
            "secoes_gap": [], "top_aliados": [], "top_lideres": [],
            "por_municipio": [], "recomendacoes": [],
        }

    secao_ids = [s["secao_id"] for s in secoes_gap]
    votos_perdidos = sum(s["v_partido"] or 0 for s in secoes_gap)

    # Top aliados: candidatos do partido com mais voto nas seções gap (ano cruzamento)
    top_aliados = db.execute(text("""
        SELECT c.nome, c.nome_urna, cd.cargo, cd.numero, cd.ano,
               cd.municipio_cod, m.nome AS municipio_nome,
               SUM(vs.votos) AS votos_no_gap,
               cd.total_votos AS votos_totais,
               COUNT(DISTINCT vs.secao_id) AS secoes_atingidas
        FROM votacao_secao vs
        JOIN candidatura cd ON cd.id = vs.candidatura_id
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN municipio m ON m.cod_ibge = cd.municipio_cod
        WHERE vs.secao_id = ANY(:ids)
          AND cd.ano = :ano
          AND cd.partido_numero = :p
        GROUP BY c.id, c.nome, c.nome_urna, cd.cargo, cd.numero, cd.ano,
                 cd.municipio_cod, m.nome, cd.total_votos
        ORDER BY votos_no_gap DESC
        LIMIT :lim
    """), {"ids": secao_ids, "ano": ano_cruzamento, "p": partido_numero, "lim": top_n}).mappings().all()

    # Top líderes locais: qualquer partido com mais voto nas seções gap (ano cruzamento)
    top_lideres = db.execute(text("""
        SELECT c.nome, c.nome_urna, cd.cargo, cd.numero, p.sigla AS partido,
               cd.municipio_cod, m.nome AS municipio_nome,
               SUM(vs.votos) AS votos_no_gap,
               cd.total_votos AS votos_totais,
               COUNT(DISTINCT vs.secao_id) AS secoes_atingidas
        FROM votacao_secao vs
        JOIN candidatura cd ON cd.id = vs.candidatura_id
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        LEFT JOIN municipio m ON m.cod_ibge = cd.municipio_cod
        WHERE vs.secao_id = ANY(:ids)
          AND cd.ano = :ano
        GROUP BY c.id, c.nome, c.nome_urna, cd.cargo, cd.numero, p.sigla,
                 cd.municipio_cod, m.nome, cd.total_votos
        ORDER BY votos_no_gap DESC
        LIMIT :lim
    """), {"ids": secao_ids, "ano": ano_cruzamento, "lim": top_n}).mappings().all()

    # Agregação por município
    por_municipio: dict[int, dict] = {}
    for s in secoes_gap:
        cod = s["municipio_cod"]
        if not cod:
            continue
        d = por_municipio.setdefault(cod, {
            "municipio_cod": cod,
            "municipio_nome": s["municipio_nome"],
            "secoes_gap": 0, "votos_partido_perdidos": 0,
        })
        d["secoes_gap"] += 1
        d["votos_partido_perdidos"] += int(s["v_partido"] or 0)
    por_municipio_list = sorted(por_municipio.values(), key=lambda x: -x["votos_partido_perdidos"])

    # Regras de recomendação
    rec: list[str] = []
    if por_municipio_list:
        top3_mun = por_municipio_list[:3]
        nomes = ", ".join(f"**{m['municipio_nome']}** ({m['votos_partido_perdidos']} votos)"
                          for m in top3_mun)
        rec.append(f"🎯 **Foco geográfico**: priorize visitas e estrutura nos municípios {nomes} — "
                   f"juntos somam {sum(m['votos_partido_perdidos'] for m in top3_mun)} votos do "
                   f"{sigla_partido} {ano_cruzamento} sem conversão para sua candidatura.")

    aliados_locais = [a for a in top_aliados if a["cargo"] in ("Vereador", "Prefeito")][:5]
    if aliados_locais:
        nomes_a = ", ".join(f"**{a['nome_urna'] or a['nome']}** ({a['cargo']} {a['municipio_nome'] or '?'})"
                            for a in aliados_locais)
        rec.append(f"🤝 **Articulação interna {sigla_partido}**: aproxime-se de {nomes_a}. "
                   "São lideranças do próprio partido com capilaridade onde sua candidatura "
                   "não chegou — naturais palanqueiros para próxima eleição.")

    outsiders = [l for l in top_lideres if (l["partido"] or "").upper() != sigla_partido.upper()][:5]
    if outsiders:
        nomes_o = ", ".join(f"**{o['nome_urna'] or o['nome']}** ({o['partido']} · {o['cargo']} {o['municipio_nome'] or ''})"
                            for o in outsiders)
        rec.append(f"⚖️ **Possíveis alianças externas**: {nomes_o}. "
                   "Dominam seções onde você foi zerado e podem ser pontes ou adversários — avalie "
                   "diálogo institucional ou fortaleça presença para neutralizar.")

    pct = (len(secoes_gap) / max(base_total + len(secoes_gap), 1)) * 100
    if pct > 30:
        rec.append(f"⚠️ **Cobertura insuficiente**: {pct:.0f}% das seções com voto {sigla_partido} {ano_cruzamento} "
                   "estão fora do seu alcance. Indica falta de presença sistêmica em uma fatia grande "
                   "do estado — investir em estrutura territorial (não só comício pontual) deve ser prioridade.")
    elif pct > 10:
        rec.append(f"📈 **Oportunidade significativa**: {pct:.0f}% das seções com voto {sigla_partido} são gaps. "
                   "Foco direcionado nesses pontos pode render rapidamente.")
    else:
        rec.append(f"✅ **Cobertura forte**: apenas {pct:.0f}% de gap. Trabalho fino em poucos pontos "
                   "específicos pode consolidar o eleitorado.")

    return {
        "kpis": {
            "secoes_gap": len(secoes_gap),
            "votos_partido_perdidos": votos_perdidos,
            "secoes_rueda": base_total,
            "municipios_gap": len(por_municipio_list),
            "pct_gap": round(pct, 1),
        },
        "secoes_gap": secoes_gap,
        "top_aliados": [dict(r) for r in top_aliados],
        "top_lideres": [dict(r) for r in top_lideres],
        "por_municipio": por_municipio_list,
        "recomendacoes": rec,
        "params": {"ano_cruzamento": ano_cruzamento, "sigla_partido": sigla_partido.upper()},
    }


@router.get("/candidatos/{candidatura_id}/locais")
def votos_por_local_candidato(
    candidatura_id: UUID,
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(text("""
        SELECT vl.local_id, vl.nome, vl.latitude, vl.longitude,
               vl.municipio_cod, m.nome AS municipio_nome,
               vl.votos,
               lv.endereco, lv.bairro, lv.zona_numero
        FROM v_votos_local vl
        LEFT JOIN municipio m ON m.cod_ibge = vl.municipio_cod
        LEFT JOIN local_votacao lv ON lv.id = vl.local_id
        WHERE vl.candidatura_id = :id
        ORDER BY vl.votos DESC
    """), {"id": str(candidatura_id)}).mappings().all()
    return [dict(r) for r in rows]
