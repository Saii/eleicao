"""
Carrega votacao por secao no banco usando psycopg.copy() para performance.
Espera: data/raw/votacao_secao_<UF>_<ano>.csv

Match NR_VOTAVEL -> candidatura_id por (ano, cargo, numero, partido_numero, municipio_cod).
Filtra: NR_VOTAVEL 95/96 (branco/nulo), votos = 0.
"""
from __future__ import annotations

import argparse
import io
import sys

import pandas as pd
import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from unidecode import unidecode

from etl.config import DB_URL_SYNC, RAW_DIR, UF


COLS = {
    "ANO_ELEICAO":      "ano",
    "NR_TURNO":         "turno",
    "DS_CARGO":         "cargo",
    "NR_VOTAVEL":       "nr_votavel",
    "CD_MUNICIPIO":     "cod_tse",
    "NM_MUNICIPIO":     "municipio_nome",
    "NR_ZONA":          "zona_numero",
    "NR_SECAO":         "nr_secao",
    "QT_VOTOS":         "votos",
}


def _norm(s: str | None) -> str:
    return unidecode(str(s or "")).lower().strip()


def carregar(engine: Engine, csv_path) -> int:
    print(f"[secao] Lendo {csv_path}")
    df = pd.read_csv(csv_path, sep=";", encoding="latin-1", dtype=str, on_bad_lines="warn", low_memory=False)
    df = df[[c for c in COLS if c in df.columns]].rename(columns={c: COLS[c] for c in COLS if c in df.columns})

    for col in ("ano", "turno", "nr_votavel", "cod_tse", "zona_numero", "nr_secao", "votos"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df = df.dropna(subset=["nr_votavel", "zona_numero", "nr_secao", "votos", "ano"])
    df = df[~df["nr_votavel"].isin([95, 96])]
    df = df[df["votos"] > 0]
    print(f"[secao] {len(df):,} linhas validas")

    # Mapas em memoria
    print("[secao] Construindo mapeamentos...")
    with engine.connect() as conn:
        munis = pd.read_sql(text("SELECT cod_ibge, nome FROM municipio"), conn)
        cands = pd.read_sql(text("""
            SELECT cd.id::text AS candidatura_id,
                   cd.ano, cd.cargo, cd.numero, cd.partido_numero, cd.municipio_cod
            FROM candidatura cd
        """), conn)
        secoes = pd.read_sql(text("""
            SELECT id AS secao_id, zona_numero, nr_secao FROM secao_eleitoral
        """), conn)

    munis["nome_norm"] = munis["nome"].map(_norm)
    df["municipio_norm"] = df["municipio_nome"].map(_norm)
    df = df.merge(
        munis[["cod_ibge", "nome_norm"]].rename(columns={"nome_norm": "municipio_norm"}),
        on="municipio_norm", how="left",
    )

    cands["cargo_norm"] = cands["cargo"].map(_norm)
    df["cargo_norm"] = df["cargo"].map(_norm)

    # Match por (ano, cargo_norm, numero, municipio_cod). Para cargos estaduais/federais
    # candidatura.municipio_cod e' NULL -> match so por (ano, cargo_norm, numero).
    df_join = df.rename(columns={"nr_votavel": "numero", "cod_ibge": "municipio_cod"})

    cands_mun = cands.dropna(subset=["municipio_cod"])
    cands_estad = cands[cands["municipio_cod"].isna()].drop(columns=["municipio_cod"])

    chaves_mun = ["ano", "cargo_norm", "numero", "municipio_cod"]
    m1 = df_join.merge(cands_mun[chaves_mun + ["candidatura_id"]], on=chaves_mun, how="left")
    matched1 = m1[m1["candidatura_id"].notna()]
    unmatched = m1[m1["candidatura_id"].isna()].drop(columns=["candidatura_id"])

    chaves_estad = ["ano", "cargo_norm", "numero"]
    m2 = unmatched.merge(cands_estad[chaves_estad + ["candidatura_id"]], on=chaves_estad, how="left")
    matched2 = m2[m2["candidatura_id"].notna()]

    final = pd.concat([matched1, matched2], ignore_index=True)
    perdidos = len(df) - len(final)
    print(f"[secao] {len(final):,} matches; {perdidos:,} sem candidatura ({perdidos*100/max(len(df),1):.1f}%)")

    # Mapeia secao_id por (zona, nr_secao)
    final = final.merge(secoes, on=["zona_numero", "nr_secao"], how="left")
    sem_secao = final["secao_id"].isna().sum()
    if sem_secao:
        print(f"[secao] AVISO: {sem_secao:,} linhas sem secao_id (rode load_locais antes)")
    final = final.dropna(subset=["secao_id"])

    # Agrega por (candidatura, secao) caso haja duplicados (turnos somados)
    grouped = (
        final.groupby(["candidatura_id", "secao_id"], as_index=False)["votos"].sum()
    )
    grouped["secao_id"] = grouped["secao_id"].astype("int64")
    grouped["votos"] = grouped["votos"].astype("int64")
    print(f"[secao] {len(grouped):,} pares unicos (candidatura, secao)")

    # Para idempotencia por ano: remover linhas das candidaturas deste ano antes do COPY
    print("[secao] COPY -> votacao_secao (preservando outros anos) ...")
    raw_url = DB_URL_SYNC.replace("postgresql+psycopg://", "postgresql://")
    anos = sorted(int(a) for a in df["ano"].dropna().unique())
    with psycopg.connect(raw_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM votacao_secao WHERE candidatura_id IN "
                "(SELECT id FROM candidatura WHERE ano = ANY(%s))",
                (anos,),
            )
            buf = io.StringIO()
            grouped[["candidatura_id", "secao_id", "votos"]].to_csv(
                buf, sep="\t", index=False, header=False
            )
            buf.seek(0)
            with cur.copy("COPY votacao_secao (candidatura_id, secao_id, votos) FROM STDIN") as copy:
                copy.write(buf.read())
        conn.commit()
    return len(grouped)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, default=2024)
    parser.add_argument("--uf", default=UF)
    args = parser.parse_args()

    csv_path = RAW_DIR / f"votacao_secao_{args.uf}_{args.ano}.csv"
    if not csv_path.exists():
        print(f"Arquivo nao encontrado: {csv_path}", file=sys.stderr)
        return 1
    engine = create_engine(DB_URL_SYNC, future=True)
    n = carregar(engine, csv_path)
    print(f"[secao] OK · {n:,} linhas em votacao_secao")
    return 0


if __name__ == "__main__":
    sys.exit(main())
