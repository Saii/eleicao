"""
Carrega `local_votacao` e `secao_eleitoral` a partir do CSV TSE.
Espera: data/raw/eleitorado_local_votacao_<UF>_<ano>.csv
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from etl.config import DB_URL_SYNC, RAW_DIR, UF


COLS = {
    "CD_MUNICIPIO":         "cod_tse",
    "NM_MUNICIPIO":         "municipio_nome",
    "NR_ZONA":              "zona_numero",
    "NR_SECAO":             "nr_secao",
    "NR_LOCAL_VOTACAO":     "nr_local",
    "NM_LOCAL_VOTACAO":     "nome",
    "DS_ENDERECO":          "endereco",
    "NM_BAIRRO":            "bairro",
    "NR_CEP":               "cep",
    "NR_LATITUDE":          "lat",
    "NR_LONGITUDE":         "lng",
}


def carregar(engine: Engine, csv_path) -> tuple[int, int]:
    print(f"[locais] Lendo {csv_path}")
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8", dtype=str, on_bad_lines="warn")
    df = df[[c for c in COLS if c in df.columns]].rename(columns={c: COLS[c] for c in COLS if c in df.columns})

    for col in ("cod_tse", "zona_numero", "nr_secao", "nr_local"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    # TSE marca ausencia como -1
    df.loc[df["lat"] == -1, "lat"] = None
    df.loc[df["lng"] == -1, "lng"] = None

    # Resolve municipio_cod (IBGE) por nome
    with engine.connect() as conn:
        munis = pd.read_sql(text("SELECT cod_ibge, nome FROM municipio"), conn)
    munis["nome_norm"] = munis["nome"].str.lower().str.strip()
    df["municipio_norm"] = df["municipio_nome"].fillna("").str.lower().str.strip()
    df = df.merge(
        munis[["cod_ibge", "nome_norm"]].rename(columns={"nome_norm": "municipio_norm"}),
        on="municipio_norm",
        how="left",
    )
    df["municipio_cod"] = df["cod_ibge"].astype("Int64")
    sem_match = df["municipio_cod"].isna().sum()
    if sem_match:
        print(f"[locais] AVISO: {sem_match} linhas sem municipio_cod")

    # Locais distintos
    locais = (
        df.dropna(subset=["nr_local", "zona_numero", "municipio_cod"])
        .drop_duplicates(subset=["nr_local", "zona_numero", "municipio_cod"])
        .copy()
    )

    inseridos_local = 0
    inseridos_secao = 0
    with engine.begin() as conn:
        # UPSERT (preserva dados de outros anos eventualmente carregados antes)
        local_id_map: dict[tuple, int] = {}
        for _, r in locais.iterrows():
            row = conn.execute(
                text("""
                    INSERT INTO local_votacao
                      (nr_local, municipio_cod, zona_numero, nome, endereco, bairro, cep,
                       latitude, longitude, fonte_geo)
                    VALUES (:nr_local, :municipio_cod, :zona_numero, :nome, :endereco, :bairro, :cep,
                            :lat, :lng, :fonte)
                    ON CONFLICT (zona_numero, nr_local, municipio_cod) DO UPDATE
                      SET nome = COALESCE(EXCLUDED.nome, local_votacao.nome),
                          endereco = COALESCE(EXCLUDED.endereco, local_votacao.endereco),
                          bairro = COALESCE(EXCLUDED.bairro, local_votacao.bairro),
                          cep = COALESCE(EXCLUDED.cep, local_votacao.cep),
                          latitude = COALESCE(local_votacao.latitude, EXCLUDED.latitude),
                          longitude = COALESCE(local_votacao.longitude, EXCLUDED.longitude),
                          fonte_geo = COALESCE(local_votacao.fonte_geo, EXCLUDED.fonte_geo)
                    RETURNING id
                """),
                {
                    "nr_local": int(r["nr_local"]),
                    "municipio_cod": int(r["municipio_cod"]),
                    "zona_numero": int(r["zona_numero"]),
                    "nome": r.get("nome"),
                    "endereco": r.get("endereco"),
                    "bairro": r.get("bairro"),
                    "cep": r.get("cep"),
                    "lat": float(r["lat"]) if pd.notna(r["lat"]) else None,
                    "lng": float(r["lng"]) if pd.notna(r["lng"]) else None,
                    "fonte": "tse" if pd.notna(r["lat"]) else None,
                },
            ).first()
            local_id_map[(int(r["zona_numero"]), int(r["nr_local"]), int(r["municipio_cod"]))] = row[0]
            inseridos_local += 1

        # Secoes (uma por linha, dedup)
        secoes = df.dropna(subset=["nr_secao", "zona_numero", "municipio_cod"]).drop_duplicates(
            subset=["nr_secao", "zona_numero"]
        )
        for _, r in secoes.iterrows():
            key = (int(r["zona_numero"]), int(r["nr_local"]), int(r["municipio_cod"]))
            local_id = local_id_map.get(key)
            conn.execute(
                text("""
                    INSERT INTO secao_eleitoral (zona_numero, nr_secao, municipio_cod, local_id)
                    VALUES (:z, :s, :m, :l)
                    ON CONFLICT (zona_numero, nr_secao) DO UPDATE
                      SET local_id = EXCLUDED.local_id,
                          municipio_cod = EXCLUDED.municipio_cod
                """),
                {"z": int(r["zona_numero"]), "s": int(r["nr_secao"]),
                 "m": int(r["municipio_cod"]), "l": local_id},
            )
            inseridos_secao += 1

    return inseridos_local, inseridos_secao


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, default=2024)
    parser.add_argument("--uf", default=UF)
    args = parser.parse_args()

    csv_path = RAW_DIR / f"eleitorado_local_votacao_{args.uf}_{args.ano}.csv"
    if not csv_path.exists():
        print(f"Arquivo nao encontrado: {csv_path}", file=sys.stderr)
        return 1
    engine = create_engine(DB_URL_SYNC, future=True)
    nl, ns = carregar(engine, csv_path)
    print(f"[locais] OK · {nl} locais, {ns} secoes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
