from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import (
    AnotacaoIn, AnotacaoOut,
    ApoiadorIn, ApoiadorOut,
    EventoIn, EventoOut,
    MetaIn, MetaOut,
)
from api.security import usuario_atual

router = APIRouter(prefix="/campanha", tags=["campanha"], dependencies=[Depends(usuario_atual)])


# ---------- Apoiadores ----------

@router.get("/apoiadores", response_model=list[ApoiadorOut])
def listar_apoiadores(
    municipio_cod: int | None = None,
    zona_numero: int | None = None,
    nivel: int | None = None,
    db: Session = Depends(get_db),
) -> list[ApoiadorOut]:
    sql = "SELECT * FROM apoiador WHERE 1=1"
    params: dict = {}
    if municipio_cod:
        sql += " AND municipio_cod = :m"; params["m"] = municipio_cod
    if zona_numero:
        sql += " AND zona_numero = :z"; params["z"] = zona_numero
    if nivel:
        sql += " AND nivel_engajamento = :n"; params["n"] = nivel
    sql += " ORDER BY criado_em DESC"
    rows = db.execute(text(sql), params).mappings().all()
    return [ApoiadorOut(**r) for r in rows]


@router.post("/apoiadores", response_model=ApoiadorOut)
def criar_apoiador(
    body: ApoiadorIn,
    db: Session = Depends(get_db),
    user: dict = Depends(usuario_atual),
) -> ApoiadorOut:
    row = db.execute(text("""
        INSERT INTO apoiador
          (nome, telefone, email, cpf, titulo_eleitor, municipio_cod, zona_numero,
           secao, bairro, endereco, nivel_engajamento, observacoes, cadastrado_por)
        VALUES (:nome, :telefone, :email, :cpf, :titulo_eleitor, :municipio_cod, :zona_numero,
                :secao, :bairro, :endereco, :nivel_engajamento, :observacoes, :uid)
        RETURNING *
    """), {**body.model_dump(), "uid": user["id"]}).mappings().first()
    db.commit()
    return ApoiadorOut(**row)


@router.delete("/apoiadores/{apoiador_id}")
def remover_apoiador(apoiador_id: UUID, db: Session = Depends(get_db)) -> dict:
    r = db.execute(text("DELETE FROM apoiador WHERE id = :i"), {"i": str(apoiador_id)})
    db.commit()
    if r.rowcount == 0:
        raise HTTPException(404, "Apoiador não encontrado")
    return {"removido": True}


# ---------- Eventos ----------

@router.get("/eventos", response_model=list[EventoOut])
def listar_eventos(db: Session = Depends(get_db)) -> list[EventoOut]:
    rows = db.execute(text("SELECT * FROM evento ORDER BY inicio DESC")).mappings().all()
    return [EventoOut(**r) for r in rows]


@router.post("/eventos", response_model=EventoOut)
def criar_evento(
    body: EventoIn,
    db: Session = Depends(get_db),
    user: dict = Depends(usuario_atual),
) -> EventoOut:
    row = db.execute(text("""
        INSERT INTO evento
          (titulo, descricao, inicio, fim, local, municipio_cod, zona_numero,
           bairro, publico_estimado, status, criado_por)
        VALUES (:titulo, :descricao, :inicio, :fim, :local, :municipio_cod, :zona_numero,
                :bairro, :publico_estimado, :status, :uid)
        RETURNING *
    """), {**body.model_dump(), "uid": user["id"]}).mappings().first()
    db.commit()
    return EventoOut(**row)


# ---------- Anotações ----------

@router.get("/anotacoes", response_model=list[AnotacaoOut])
def listar_anotacoes(
    municipio_cod: int | None = None,
    zona_numero: int | None = None,
    db: Session = Depends(get_db),
) -> list[AnotacaoOut]:
    sql = "SELECT * FROM anotacao WHERE 1=1"
    params: dict = {}
    if municipio_cod:
        sql += " AND municipio_cod = :m"; params["m"] = municipio_cod
    if zona_numero:
        sql += " AND zona_numero = :z"; params["z"] = zona_numero
    sql += " ORDER BY criado_em DESC"
    rows = db.execute(text(sql), params).mappings().all()
    return [AnotacaoOut(**r) for r in rows]


@router.post("/anotacoes", response_model=AnotacaoOut)
def criar_anotacao(
    body: AnotacaoIn,
    db: Session = Depends(get_db),
    user: dict = Depends(usuario_atual),
) -> AnotacaoOut:
    row = db.execute(text("""
        INSERT INTO anotacao
          (titulo, conteudo, municipio_cod, zona_numero, bairro, tags, criado_por)
        VALUES (:titulo, :conteudo, :municipio_cod, :zona_numero, :bairro, :tags, :uid)
        RETURNING *
    """), {**body.model_dump(), "uid": user["id"]}).mappings().first()
    db.commit()
    return AnotacaoOut(**row)


# ---------- Metas ----------

@router.get("/metas", response_model=list[MetaOut])
def listar_metas(db: Session = Depends(get_db)) -> list[MetaOut]:
    rows = db.execute(text("SELECT * FROM meta ORDER BY criado_em DESC")).mappings().all()
    return [MetaOut(**r) for r in rows]


@router.post("/metas", response_model=MetaOut)
def criar_meta(
    body: MetaIn,
    db: Session = Depends(get_db),
    user: dict = Depends(usuario_atual),
) -> MetaOut:
    row = db.execute(text("""
        INSERT INTO meta
          (descricao, municipio_cod, zona_numero, votos_alvo, apoiadores_alvo,
           prazo, status, responsavel)
        VALUES (:descricao, :municipio_cod, :zona_numero, :votos_alvo, :apoiadores_alvo,
                :prazo, :status, :uid)
        RETURNING *
    """), {**body.model_dump(), "uid": user["id"]}).mappings().first()
    db.commit()
    return MetaOut(**row)
