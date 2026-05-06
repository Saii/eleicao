"""
Cria/atualiza o usuário admin em produção via DB_URL.
Uso (com prompt):
  python -m scripts.create_admin_prod

Ou direto:
  python -m scripts.create_admin_prod --email admin@x.com --senha "..." --db-url "postgresql+psycopg://..."
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

import bcrypt
from sqlalchemy import create_engine, text


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=False)
    p.add_argument("--senha", required=False)
    p.add_argument("--nome", default="Admin")
    p.add_argument("--db-url", required=False)
    args = p.parse_args()

    db_url = args.db_url or os.getenv("DB_URL_SYNC") or os.getenv("DB_URL")
    if not db_url:
        print("Defina --db-url ou DB_URL_SYNC.", file=sys.stderr)
        return 1

    email = args.email or input("E-mail: ").strip()
    senha = args.senha or getpass.getpass("Senha (mín 8): ")
    if len(senha) < 8:
        print("Senha precisa ter pelo menos 8 caracteres.", file=sys.stderr)
        return 1

    h = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO usuario (email, nome, senha_hash, papel, ativo)
            VALUES (:e, :n, :h, 'admin', TRUE)
            ON CONFLICT (email) DO UPDATE SET
                senha_hash = EXCLUDED.senha_hash,
                nome = EXCLUDED.nome,
                ativo = TRUE
        """), {"e": email, "n": args.nome, "h": h})
    print(f"OK · admin {email} pronto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
