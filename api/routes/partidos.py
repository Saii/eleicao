from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import CandidatoBusca, Partido
from api.security import usuario_atual

router = APIRouter(prefix="/partidos", tags=["partidos"],
                   dependencies=[Depends(usuario_atual)])


@router.get("", response_model=list[Partido])
def listar(db: Session = Depends(get_db)) -> list[Partido]:
    rows = db.execute(text("SELECT numero, sigla, nome FROM partido ORDER BY sigla")).mappings().all()
    return [Partido(**r) for r in rows]


@router.get("/{sigla}/agregado")
def agregado_por_partido(sigla: str, ano: int, db: Session = Depends(get_db)) -> dict:
    """Total de votos do partido por município no ano dado."""
    rows = db.execute(text("""
        SELECT m.cod_ibge, m.nome AS municipio, SUM(v.votos) AS votos
        FROM votacao v
        JOIN candidatura cd ON cd.id = v.candidatura_id
        JOIN partido p ON p.numero = cd.partido_numero
        LEFT JOIN municipio m ON m.cod_ibge = v.municipio_cod
        WHERE p.sigla = :s AND cd.ano = :ano
        GROUP BY m.cod_ibge, m.nome
        ORDER BY votos DESC
    """), {"s": sigla.upper(), "ano": ano}).mappings().all()
    total = sum(r["votos"] or 0 for r in rows)
    return {"sigla": sigla.upper(), "ano": ano, "total": total, "municipios": [dict(r) for r in rows]}


@router.get("/{sigla}/candidatos", response_model=list[CandidatoBusca])
def candidatos_do_partido(
    sigla: str,
    ano: int | None = None,
    cargo: str | None = None,
    apenas_eleitos: bool = False,
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
) -> list[CandidatoBusca]:
    sql = """
        SELECT cd.id AS candidatura_id, c.id AS candidato_id,
               c.nome, c.nome_urna, cd.ano, cd.cargo, cd.numero,
               p.sigla AS partido_sigla, cd.total_votos
        FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        JOIN partido p ON p.numero = cd.partido_numero
        WHERE p.sigla = :s
    """
    params: dict = {"s": sigla.upper(), "lim": limit}
    if ano:
        sql += " AND cd.ano = :ano"; params["ano"] = ano
    if cargo:
        sql += " AND cd.cargo ILIKE :c"; params["c"] = f"%{cargo}%"
    if apenas_eleitos:
        sql += " AND cd.situacao ILIKE 'ELEIT%'"
    sql += " ORDER BY cd.total_votos DESC LIMIT :lim"
    rows = db.execute(text(sql), params).mappings().all()
    return [CandidatoBusca(**r) for r in rows]


@router.get("/{sigla}/filiacao")
def filiacao_perfil(
    sigla: str,
    municipio_cod: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Agregados de filiacao do partido (por municipio, zona e demografia)."""
    base_sql = """
        SELECT fp.partido_numero, p.sigla AS partido_sigla,
               fp.municipio_cod, m.nome AS municipio_nome,
               fp.zona_numero,
               fp.ds_genero, fp.ds_faixa_etaria,
               fp.ds_estado_civil, fp.ds_grau_instrucao,
               fp.qt_filiado, fp.nr_ano_mes
        FROM filiacao_perfil fp
        JOIN partido p ON p.numero = fp.partido_numero
        LEFT JOIN municipio m ON m.cod_ibge = fp.municipio_cod
        WHERE p.sigla = :s
    """
    params: dict = {"s": sigla.upper()}
    if municipio_cod:
        base_sql += " AND fp.municipio_cod = :m"; params["m"] = municipio_cod
    linhas = db.execute(text(base_sql), params).mappings().all()

    total = sum(r["qt_filiado"] or 0 for r in linhas)
    por_mun: dict[int, dict] = {}
    por_genero: dict[str, int] = {}
    por_idade: dict[str, int] = {}
    ref = 0
    for r in linhas:
        mc = r["municipio_cod"]
        if mc:
            d = por_mun.setdefault(mc, {"municipio_cod": mc, "municipio_nome": r["municipio_nome"], "qt_filiado": 0})
            d["qt_filiado"] += r["qt_filiado"] or 0
        if r["ds_genero"]:
            por_genero[r["ds_genero"]] = por_genero.get(r["ds_genero"], 0) + (r["qt_filiado"] or 0)
        if r["ds_faixa_etaria"]:
            por_idade[r["ds_faixa_etaria"]] = por_idade.get(r["ds_faixa_etaria"], 0) + (r["qt_filiado"] or 0)
        if r["nr_ano_mes"] and r["nr_ano_mes"] > ref:
            ref = r["nr_ano_mes"]
    return {
        "sigla": sigla.upper(),
        "ref": ref,
        "total": total,
        "por_municipio": sorted(por_mun.values(), key=lambda x: -x["qt_filiado"]),
        "por_genero": [{"chave": k, "qt": v} for k, v in sorted(por_genero.items(), key=lambda kv: -kv[1])],
        "por_faixa_etaria": [{"chave": k, "qt": v} for k, v in sorted(por_idade.items(), key=lambda kv: -kv[1])],
    }
