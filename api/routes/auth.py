from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import LoginIn, TokenOut, UsuarioCreate, UsuarioOut
from api.security import criar_token, exige_papel, hash_senha, verificar_senha, usuario_atual

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    row = db.execute(
        text("SELECT id, senha_hash, papel, ativo FROM usuario WHERE email = :e"),
        {"e": body.email},
    ).mappings().first()
    if not row or not row["ativo"] or not verificar_senha(body.senha, row["senha_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = criar_token(str(row["id"]), row["papel"])
    return TokenOut(access_token=token)


@router.get("/me", response_model=UsuarioOut)
def me(user: dict = Depends(usuario_atual)) -> UsuarioOut:
    return UsuarioOut(**user)


@router.post("/usuarios", response_model=UsuarioOut, dependencies=[Depends(exige_papel("admin"))])
def criar_usuario(body: UsuarioCreate, db: Session = Depends(get_db)) -> UsuarioOut:
    row = db.execute(
        text("""
            INSERT INTO usuario (email, nome, senha_hash, papel)
            VALUES (:e, :n, :h, :p)
            RETURNING id, email, nome, papel, ativo
        """),
        {"e": body.email, "n": body.nome, "h": hash_senha(body.senha), "p": body.papel},
    ).mappings().first()
    db.commit()
    return UsuarioOut(**row)
