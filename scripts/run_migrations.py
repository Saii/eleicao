"""
Aplica schema.sql + seeds + todas as migrations contra um Postgres alvo.
Uso:
  python -m scripts.run_migrations            # usa DB_URL_SYNC do .env
  DB_URL_SYNC=postgresql+psycopg://... python -m scripts.run_migrations
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


def main() -> int:
    db_url = os.getenv("DB_URL_SYNC") or os.getenv("DB_URL")
    if not db_url:
        print("ERRO: defina DB_URL_SYNC ou DB_URL", file=sys.stderr)
        return 1

    base = Path(__file__).resolve().parent.parent
    arquivos: list[Path] = [
        base / "db" / "schema.sql",
        base / "db" / "seed_partidos.sql",
    ]
    migrations_dir = base / "db" / "migrations"
    if migrations_dir.exists():
        arquivos.extend(sorted(migrations_dir.glob("*.sql")))

    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        for arq in arquivos:
            if not arq.exists():
                continue
            sql = arq.read_text(encoding="utf-8")
            print(f"[migrate] aplicando {arq.name} ({len(sql)} chars)")
            for stmt in sql.split(";\n"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        # Tolera erros em ALTER TABLE / CREATE INDEX já existentes
                        msg = str(e).lower()
                        if "already exists" in msg or "duplicate" in msg or "exists" in msg:
                            print(f"  (skip — já existe)")
                        else:
                            raise
    print("[migrate] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
