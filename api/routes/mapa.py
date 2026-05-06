from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.security import usuario_atual

router = APIRouter(prefix="/mapa", tags=["mapa"],
                   dependencies=[Depends(usuario_atual)])


@router.get("/municipios.geojson")
def municipios_geojson(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(text("""
        SELECT cod_ibge, nome, geom AS geometry
        FROM municipio
        WHERE geom IS NOT NULL
    """)).mappings().all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": r["cod_ibge"],
                "properties": {"cod_ibge": r["cod_ibge"], "nome": r["nome"]},
                "geometry": r["geometry"],
            }
            for r in rows
        ],
    }


@router.get("/votos-municipio")
def votos_por_municipio(
    candidatura_id: str | None = None,
    sigla_partido: str | None = None,
    ano: int | None = None,
    cargo: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Agregado de votos por município. Filtros combináveis."""
    sql = """
        SELECT m.cod_ibge, m.nome AS municipio, COALESCE(SUM(v.votos), 0) AS votos
        FROM municipio m
        LEFT JOIN votacao v ON v.municipio_cod = m.cod_ibge
        LEFT JOIN candidatura cd ON cd.id = v.candidatura_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE 1=1
    """
    params: dict = {}
    if candidatura_id:
        sql += " AND cd.id = :cid"; params["cid"] = candidatura_id
    if sigla_partido:
        sql += " AND p.sigla = :s"; params["s"] = sigla_partido.upper()
    if ano:
        sql += " AND cd.ano = :ano"; params["ano"] = ano
    if cargo:
        sql += " AND cd.cargo ILIKE :c"; params["c"] = f"%{cargo}%"
    sql += " GROUP BY m.cod_ibge, m.nome ORDER BY votos DESC"
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]
