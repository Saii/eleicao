"""
Carrega dados normalizados (parquet) e GeoJSON IBGE no Postgres.
Pré-requisitos:
  - schema.sql aplicado
  - seed_partidos.sql aplicado
  - etl.ibge_download e etl.normalize executados
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from unidecode import unidecode

from etl.config import DB_URL_SYNC, GEO_DIR, PROCESSED_DIR, UF


def _norm(s: str) -> str:
    return unidecode(str(s)).lower().strip()


def carregar_municipios(engine: Engine) -> dict[str, int]:
    geojson_path = GEO_DIR / f"municipios_{UF}.geojson"
    meta_path = PROCESSED_DIR / f"municipios_{UF}.parquet"
    if not geojson_path.exists() or not meta_path.exists():
        raise FileNotFoundError("Execute etl.ibge_download primeiro.")

    geo = json.loads(geojson_path.read_text(encoding="utf-8"))
    meta = pd.read_parquet(meta_path)
    nome_por_cod = dict(zip(meta["cod_ibge"], meta["nome"]))

    print(f"[db] {len(geo['features'])} municípios no GeoJSON")
    with engine.begin() as conn:
        for feat in geo["features"]:
            cod = int(feat["properties"].get("codarea") or feat["id"])
            nome = nome_por_cod.get(cod, feat["properties"].get("name", ""))
            geom_json = json.dumps(feat["geometry"])
            conn.execute(
                text("""
                    INSERT INTO municipio (cod_ibge, nome, nome_normalizado, geom)
                    VALUES (:cod, :nome, :norm, CAST(:geom AS JSONB))
                    ON CONFLICT (cod_ibge) DO UPDATE
                      SET nome = EXCLUDED.nome,
                          nome_normalizado = EXCLUDED.nome_normalizado,
                          geom = EXCLUDED.geom
                """),
                {"cod": cod, "nome": nome, "norm": _norm(nome), "geom": geom_json},
            )
    print("[db] municípios OK")

    # mapa nome_normalizado → cod_ibge para fazer link com TSE
    return {_norm(n): c for c, n in nome_por_cod.items()}


def carregar_partidos_observados(engine: Engine, candidatos: pd.DataFrame) -> None:
    df = (
        candidatos[["partido_numero", "partido_sigla", "partido_nome"]]
        .dropna(subset=["partido_numero"])
        .drop_duplicates(subset=["partido_numero"])
    )
    with engine.begin() as conn:
        for _, r in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO partido (numero, sigla, nome)
                    VALUES (:n, :s, :nm)
                    ON CONFLICT (numero) DO UPDATE
                      SET sigla = EXCLUDED.sigla, nome = EXCLUDED.nome
                """),
                {"n": int(r["partido_numero"]),
                 "s": r["partido_sigla"] or "",
                 "nm": r["partido_nome"] or r["partido_sigla"] or ""},
            )
    print(f"[db] {len(df)} partidos atualizados")


def carregar_candidatos_e_votacoes(
    engine: Engine,
    nome_para_cod: dict[str, int],
) -> None:
    cand = pd.read_parquet(PROCESSED_DIR / "candidatos.parquet")
    vot = pd.read_parquet(PROCESSED_DIR / "votacoes.parquet")
    print(f"[db] candidatos={len(cand)}  votacoes={len(vot)}")

    if "nascimento" not in cand.columns:
        cand["nascimento"] = None
    if "nome_normalizado" not in cand.columns:
        cand["nome_normalizado"] = cand["nome"].fillna("").map(_norm)
    cand["pessoa_key"] = cand["nome_normalizado"].fillna("").astype(str)
    cand = cand[cand["pessoa_key"].str.len() > 0].copy()

    with engine.begin() as conn:
        # Recarga total das tabelas eleitorais derivadas do TSE
        conn.execute(text("TRUNCATE TABLE votacao, candidatura, candidato RESTART IDENTITY CASCADE"))

        # 1) candidatos (pessoa)
        pessoa_id_map: dict[str, str] = {}
        for key, grp in cand.groupby("pessoa_key"):
            r = grp.iloc[0]
            row = conn.execute(
                text("""
                    INSERT INTO candidato (nome, nome_normalizado, nome_urna, nascimento, genero)
                    VALUES (:n, :norm, :u, :nasc, :g)
                    RETURNING id
                """),
                {
                    "n": r["nome"],
                    "norm": _norm(r["nome"]),
                    "u": r.get("nome_urna"),
                    "nasc": None if pd.isna(r.get("nascimento")) else r.get("nascimento"),
                    "g": r.get("genero"),
                },
            ).first()
            pessoa_id_map[key] = str(row[0])
        print(f"[db] {len(pessoa_id_map)} candidatos (pessoas) inseridos")

        # 2) candidaturas
        candidatura_id_map: dict[tuple, str] = {}
        for _, r in cand.iterrows():
            row = conn.execute(
                text("""
                    INSERT INTO candidatura
                      (candidato_id, ano, turno, cargo, numero,
                       partido_numero, coligacao, municipio_cod, situacao)
                    VALUES (:pid, :ano, :turno, :cargo, :num,
                            :pnum, :col, :mun, :sit)
                    ON CONFLICT (ano, turno, cargo, candidato_id) DO UPDATE
                      SET partido_numero = EXCLUDED.partido_numero
                    RETURNING id
                """),
                {
                    "pid": pessoa_id_map[r["pessoa_key"]],
                    "ano": int(r["ano"]),
                    "turno": int(r.get("turno") or 1),
                    "cargo": r.get("cargo") or "",
                    "num": int(r.get("numero") or 0),
                    "pnum": int(r["partido_numero"]) if pd.notna(r.get("partido_numero")) else None,
                    "col": r.get("coligacao"),
                    "mun": None,
                    "sit": r.get("situacao"),
                },
            ).first()
            candidatura_id_map[(int(r["ano"]), int(r.get("turno") or 1), str(r["sq_candidato"]))] = str(row[0])
        print(f"[db] {len(candidatura_id_map)} candidaturas inseridas")

        # 3) votações
        nome_mun_para_cod = {_norm(k): v for k, v in nome_para_cod.items()}
        inseridas = 0
        for _, r in vot.iterrows():
            key = (int(r["ano"]), int(r.get("turno") or 1), str(r["sq_candidato"]))
            cid = candidatura_id_map.get(key)
            if not cid:
                continue
            mun_cod = nome_mun_para_cod.get(_norm(r.get("municipio_nome", "")))
            conn.execute(
                text("""
                    INSERT INTO votacao (candidatura_id, zona_numero, municipio_cod, votos)
                    VALUES (:cid, :z, :m, :v)
                    ON CONFLICT (candidatura_id, zona_numero, municipio_cod)
                    DO UPDATE SET votos = EXCLUDED.votos
                """),
                {"cid": cid,
                 "z": int(r.get("zona_numero") or 0),
                 "m": mun_cod,
                 "v": int(r.get("votos") or 0)},
            )
            inseridas += 1
        print(f"[db] {inseridas} linhas de votacao inseridas")

        # totais por candidatura
        conn.execute(text("""
            UPDATE candidatura cd
            SET total_votos = sub.t
            FROM (SELECT candidatura_id, SUM(votos) t FROM votacao GROUP BY 1) sub
            WHERE cd.id = sub.candidatura_id
        """))


def main() -> int:
    if not DB_URL_SYNC:
        print("DB_URL_SYNC ausente.", file=sys.stderr)
        return 1
    engine = create_engine(DB_URL_SYNC, future=True)

    nome_para_cod = carregar_municipios(engine)

    cand_path = PROCESSED_DIR / "candidatos.parquet"
    if cand_path.exists():
        candidatos = pd.read_parquet(cand_path)
        carregar_partidos_observados(engine, candidatos)
        carregar_candidatos_e_votacoes(engine, nome_para_cod)
    else:
        print("[db] Pulando candidatos (rode etl.normalize antes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
