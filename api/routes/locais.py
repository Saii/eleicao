from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.security import usuario_atual

router = APIRouter(prefix="/locais-votacao", tags=["locais"],
                   dependencies=[Depends(usuario_atual)])


@router.get("")
def listar(
    municipio_cod: int | None = None,
    zona_numero: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    sql = """
        SELECT lv.id, lv.nr_local, lv.municipio_cod, m.nome AS municipio_nome,
               lv.zona_numero, lv.nome, lv.endereco, lv.bairro, lv.cep,
               lv.latitude, lv.longitude, lv.fonte_geo
        FROM local_votacao lv
        LEFT JOIN municipio m ON m.cod_ibge = lv.municipio_cod
        WHERE 1=1
    """
    params: dict = {}
    if municipio_cod:
        sql += " AND lv.municipio_cod = :m"; params["m"] = municipio_cod
    if zona_numero:
        sql += " AND lv.zona_numero = :z"; params["z"] = zona_numero
    sql += " ORDER BY lv.municipio_cod, lv.zona_numero, lv.nr_local"
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{local_id}")
def detalhe(local_id: int, db: Session = Depends(get_db)) -> dict:
    head = db.execute(text("""
        SELECT lv.*, m.nome AS municipio_nome
        FROM local_votacao lv
        LEFT JOIN municipio m ON m.cod_ibge = lv.municipio_cod
        WHERE lv.id = :id
    """), {"id": local_id}).mappings().first()
    if not head:
        raise HTTPException(404, "Local nao encontrado")
    secoes = db.execute(text("""
        SELECT zona_numero, nr_secao FROM secao_eleitoral
        WHERE local_id = :id ORDER BY zona_numero, nr_secao
    """), {"id": local_id}).mappings().all()
    return {**dict(head), "secoes": [dict(s) for s in secoes]}


@router.get("/_resumo/{municipio_cod}")
def resumo_municipio(municipio_cod: int, db: Session = Depends(get_db)) -> dict:
    """Quantos locais com/sem coords no municipio."""
    row = db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(latitude) AS com_coords,
            COUNT(*) FILTER (WHERE latitude IS NULL) AS sem_coords
        FROM local_votacao
        WHERE municipio_cod = :m
    """), {"m": municipio_cod}).mappings().first()
    return dict(row) if row else {"total": 0, "com_coords": 0, "sem_coords": 0}
