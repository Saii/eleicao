"""
Carrega o CSV agregado de perfil de filiacao partidaria (data/raw/perfil_filiacao_<UF>.csv)
na tabela `filiacao_perfil` do Postgres.

Pre-req: migration 003 aplicada e tse_filiados executado.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from etl.config import DB_URL_SYNC, RAW_DIR, UF


COLS = {
    "NR_ANO_MES":       "nr_ano_mes",
    "NR_PARTIDO":       "partido_numero",
    "SG_PARTIDO":       "partido_sigla",
    "CD_MUNICIPIO":     "cod_tse",
    "NM_MUNICIPIO":     "municipio_nome",
    "NR_ZONA":          "zona_numero",
    "DS_GENERO":        "ds_genero",
    "DS_FAIXA_ETARIA":  "ds_faixa_etaria",
    "DS_ESTADO_CIVIL":  "ds_estado_civil",
    "DS_GRAU_INSTRUCAO": "ds_grau_instrucao",
    "QT_FILIADO":       "qt_filiado",
}


def carregar(engine: Engine, csv_path: Path) -> int:
    print(f"[filiacao] Lendo {csv_path}")
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8", dtype=str, on_bad_lines="warn")
    df = df[[c for c in COLS if c in df.columns]].rename(columns={c: COLS[c] for c in COLS if c in df.columns})

    for col in ("nr_ano_mes", "partido_numero", "cod_tse", "zona_numero", "qt_filiado"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Resolve municipio_cod (IBGE) a partir do NM_MUNICIPIO via tabela municipio
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
        print(f"[filiacao] AVISO: {sem_match} linhas sem match de municipio (provavel UF errada)")

    df = df.dropna(subset=["partido_numero", "qt_filiado"])
    df["snapshot_em"] = date.today()

    # Insere partidos novos (numero pode existir com sigla diferente)
    partidos_csv = (
        df.dropna(subset=["partido_numero", "partido_sigla"])
        [["partido_numero", "partido_sigla"]]
        .drop_duplicates()
    )
    with engine.connect() as conn:
        existentes = set(conn.execute(text("SELECT numero FROM partido")).scalars())
        siglas_existentes = set(conn.execute(text("SELECT sigla FROM partido")).scalars())
    novos = partidos_csv[~partidos_csv["partido_numero"].astype(int).isin(existentes)]
    with engine.begin() as conn:
        for _, p in novos.iterrows():
            sigla = p["partido_sigla"]
            if sigla in siglas_existentes:
                sigla = f"{sigla}_{int(p['partido_numero'])}"  # desambigua
            conn.execute(
                text("INSERT INTO partido (numero, sigla, nome) VALUES (:n, :s, :nm) ON CONFLICT DO NOTHING"),
                {"n": int(p["partido_numero"]), "s": sigla, "nm": p["partido_sigla"]},
            )
            siglas_existentes.add(sigla)

    # Filtra linhas cujo partido nao foi inserido (improvavel apos a etapa acima)
    with engine.connect() as conn:
        validos = set(conn.execute(text("SELECT numero FROM partido")).scalars())
    antes = len(df)
    df = df[df["partido_numero"].astype(int).isin(validos)]
    descartados = antes - len(df)
    if descartados:
        print(f"[filiacao] {descartados} linhas descartadas (partido inexistente)")

    print(f"[filiacao] {len(df)} linhas para inserir")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE filiacao_perfil RESTART IDENTITY"))
        rows = df[[
            "partido_numero", "municipio_cod", "zona_numero",
            "ds_genero", "ds_faixa_etaria", "ds_estado_civil", "ds_grau_instrucao",
            "qt_filiado", "nr_ano_mes", "snapshot_em",
        ]].to_dict(orient="records")
        # bulk insert por chunks
        chunk = 5000
        for i in range(0, len(rows), chunk):
            conn.execute(
                text("""
                    INSERT INTO filiacao_perfil
                      (partido_numero, municipio_cod, zona_numero,
                       ds_genero, ds_faixa_etaria, ds_estado_civil, ds_grau_instrucao,
                       qt_filiado, nr_ano_mes, snapshot_em)
                    VALUES
                      (:partido_numero, :municipio_cod, :zona_numero,
                       :ds_genero, :ds_faixa_etaria, :ds_estado_civil, :ds_grau_instrucao,
                       :qt_filiado, :nr_ano_mes, :snapshot_em)
                """),
                rows[i:i + chunk],
            )
    return len(df)


def main() -> int:
    csv_path = RAW_DIR / f"perfil_filiacao_{UF}.csv"
    if not csv_path.exists():
        print(f"Arquivo nao encontrado: {csv_path}. Rode etl.tse_filiados primeiro.", file=sys.stderr)
        return 1
    engine = create_engine(DB_URL_SYNC, future=True)
    n = carregar(engine, csv_path)
    print(f"[filiacao] OK · {n} linhas carregadas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
