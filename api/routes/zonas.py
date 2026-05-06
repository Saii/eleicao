from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.security import usuario_atual

router = APIRouter(prefix="/zonas", tags=["zonas"],
                   dependencies=[Depends(usuario_atual)])


@router.get("/{numero}/top")
def top_candidatos_na_zona(
    numero: int,
    ano: int,
    cargo: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[dict]:
    sql = """
        SELECT c.nome, c.nome_urna, p.sigla AS partido,
               cd.numero, cd.cargo, v.votos
        FROM votacao v
        JOIN candidatura cd ON cd.id = v.candidatura_id
        JOIN candidato c ON c.id = cd.candidato_id
        LEFT JOIN partido p ON p.numero = cd.partido_numero
        WHERE v.zona_numero = :z AND cd.ano = :ano
    """
    params: dict = {"z": numero, "ano": ano, "lim": limit}
    if cargo:
        sql += " AND cd.cargo ILIKE :cargo"; params["cargo"] = f"%{cargo}%"
    sql += " ORDER BY v.votos DESC LIMIT :lim"
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]
