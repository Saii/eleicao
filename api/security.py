from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_senha(s: str) -> str:
    return bcrypt.hashpw(s.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(s: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(s.encode("utf-8"), h.encode("utf-8"))
    except ValueError:
        return False


def criar_token(sub: str, papel: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MIN)
    payload = {"sub": sub, "papel": papel, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def usuario_atual(
    token: str = Depends(oauth2),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise cred_exc
    except JWTError as exc:
        raise cred_exc from exc

    row = db.execute(
        text("SELECT id, email, nome, papel, ativo FROM usuario WHERE id = :id"),
        {"id": user_id},
    ).mappings().first()
    if not row or not row["ativo"]:
        raise cred_exc
    return dict(row)


def exige_papel(*papeis: str):
    def _dep(user: dict = Depends(usuario_atual)) -> dict:
        if user["papel"] not in papeis:
            raise HTTPException(status_code=403, detail="Sem permissão")
        return user
    return _dep
