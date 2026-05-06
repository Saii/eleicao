from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import CandidatoBusca, CandidatoDetalhe, VotoZona
from api.security import usuario_atual

router = APIRouter(prefix="/candidatos", tags=["candidatos"],
                   dependencies=[Depends(usuario_atual)])


@router.get("", response_model=list[CandidatoBusca])
def buscar(
    q: str | None = Query(None, description="Trecho do nome ou nome de urna"),
    ano: int | None = None,
    cargo: str | None = None,
    partido: str | None = None,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
) -> list[CandidatoBusca]:
    sql = """
        SELECT cd.id AS candidatura_id, c.id AS candidato_id,
               c.nome, c.nome_urna, cd.ano, cd.cargo, cd.numero,
               p.sigla AS partido_sigla, cd.total_votos
        FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE 1=1
    """
    params: dict = {}
    if q:
        sql += " AND (c.nome_normalizado ILIKE :q OR c.nome_urna ILIKE :q)"
        params["q"] = f"%{q.lower()}%"
    if ano:
        sql += " AND cd.ano = :ano"; params["ano"] = ano
    if cargo:
        sql += " AND cd.cargo ILIKE :cargo"; params["cargo"] = f"%{cargo}%"
    if partido:
        sql += " AND p.sigla = :p"; params["p"] = partido.upper()
    sql += " ORDER BY cd.total_votos DESC LIMIT :lim"
    params["lim"] = limit

    rows = db.execute(text(sql), params).mappings().all()
    return [CandidatoBusca(**r) for r in rows]


@router.get("/cargos", response_model=list[str])
def cargos_disponiveis(ano: int | None = None, db: Session = Depends(get_db)) -> list[str]:
    """Lista cargos distintos presentes nas candidaturas, opcionalmente filtrado por ano."""
    sql = "SELECT DISTINCT cargo FROM candidatura WHERE cargo IS NOT NULL AND cargo <> ''"
    params: dict = {}
    if ano:
        sql += " AND ano = :ano"
        params["ano"] = ano
    sql += " ORDER BY cargo"
    rows = db.execute(text(sql), params).all()
    return [r[0] for r in rows]


@router.get("/rueda", response_model=list[CandidatoBusca])
def rueda(db: Session = Depends(get_db)) -> list[CandidatoBusca]:
    """Atalho: todas as candidaturas do Fábio Rueda (todos os anos disponíveis)."""
    rows = db.execute(text("""
        SELECT cd.id AS candidatura_id, c.id AS candidato_id,
               c.nome, c.nome_urna, cd.ano, cd.cargo, cd.numero,
               p.sigla AS partido_sigla, cd.total_votos
        FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE c.nome_normalizado ILIKE '%rueda%'
           OR c.nome_urna ILIKE '%rueda%'
        ORDER BY cd.ano DESC, cd.total_votos DESC
    """)).mappings().all()
    return [CandidatoBusca(**r) for r in rows]


@router.get("/{candidatura_id}", response_model=CandidatoDetalhe)
def detalhe(candidatura_id: UUID, db: Session = Depends(get_db)) -> CandidatoDetalhe:
    head = db.execute(text("""
        SELECT cd.id AS candidatura_id, c.nome, c.nome_urna,
               cd.ano, cd.cargo, cd.numero, p.sigla AS partido_sigla,
               cd.coligacao, cd.situacao, cd.total_votos
        FROM candidatura cd
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE cd.id = :id
    """), {"id": str(candidatura_id)}).mappings().first()
    if not head:
        raise HTTPException(404, "Candidatura não encontrada")

    zonas = db.execute(text("""
        SELECT v.municipio_cod, m.nome AS municipio_nome, v.zona_numero, v.votos
        FROM votacao v
        LEFT JOIN municipio m ON m.cod_ibge = v.municipio_cod
        WHERE v.candidatura_id = :id
        ORDER BY v.votos DESC
    """), {"id": str(candidatura_id)}).mappings().all()

    return CandidatoDetalhe(
        **head,
        por_zona=[VotoZona(**z) for z in zonas],
    )
