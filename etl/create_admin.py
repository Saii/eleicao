"""
Cria (ou atualiza) o usuário admin inicial.
Uso:
  python -m etl.create_admin --email admin@local --senha trocar123 --nome "Admin"
Sem args, pede via prompt.
"""
from __future__ import annotations

import argparse
import getpass
import sys

import bcrypt
from sqlalchemy import create_engine, text

from etl.config import DB_URL_SYNC


def _hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email")
    parser.add_argument("--senha")
    parser.add_argument("--nome", default="Admin")
    parser.add_argument("--papel", default="admin", choices=["admin", "coordenador", "membro"])
    args = parser.parse_args()

    email = args.email or input("E-mail: ").strip()
    senha = args.senha or getpass.getpass("Senha: ")
    if len(senha) < 8:
        print("Senha precisa ter pelo menos 8 caracteres.", file=sys.stderr)
        return 1

    engine = create_engine(DB_URL_SYNC, future=True)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO usuario (email, nome, senha_hash, papel, ativo)
            VALUES (:e, :n, :h, :p, TRUE)
            ON CONFLICT (email) DO UPDATE SET
                nome = EXCLUDED.nome,
                senha_hash = EXCLUDED.senha_hash,
                papel = EXCLUDED.papel,
                ativo = TRUE
        """), {"e": email, "n": args.nome, "h": _hash(senha), "p": args.papel})
    print(f"OK · usuário {email} ({args.papel}) pronto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
