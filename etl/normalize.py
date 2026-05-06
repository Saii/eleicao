"""
Normaliza CSVs brutos do TSE em dataframes parquet limpos.
Saída em data/processed/:
  - candidatos.parquet      (1 linha por candidatura)
  - votacoes.parquet        (1 linha por candidatura x zona x municipio)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from unidecode import unidecode

from etl.config import ANOS, PROCESSED_DIR, RAW_DIR, UF

# Colunas relevantes do layout TSE (votacao_candidato_munzona)
COLS = {
    "ANO_ELEICAO":        "ano",
    "NR_TURNO":           "turno",
    "DS_CARGO":           "cargo",
    "SQ_CANDIDATO":       "sq_candidato",
    "NM_CANDIDATO":       "nome",
    "NM_URNA_CANDIDATO":  "nome_urna",
    "NR_CANDIDATO":       "numero",
    "NR_PARTIDO":         "partido_numero",
    "SG_PARTIDO":         "partido_sigla",
    "NM_PARTIDO":         "partido_nome",
    "NM_COLIGACAO":       "coligacao",
    "DS_SIT_TOT_TURNO":   "situacao",
    "CD_MUNICIPIO":       "cod_tse",
    "NM_MUNICIPIO":       "municipio_nome",
    "NR_ZONA":            "zona_numero",
    "QT_VOTOS_NOMINAIS":  "votos",
    "DS_GENERO":          "genero",
    "DT_NASCIMENTO":      "nascimento",
}


def _norm(s: str) -> str:
    return unidecode(str(s)).lower().strip()


def carregar_csv(path: Path) -> pd.DataFrame:
    print(f"[normalize] {path.name}")
    df = pd.read_csv(
        path,
        sep=";",
        encoding="latin-1",
        dtype=str,
        on_bad_lines="warn",
        low_memory=False,
    )
    presentes = [c for c in COLS if c in df.columns]
    df = df[presentes].rename(columns={c: COLS[c] for c in presentes})
    # tipagem
    for col in ("ano", "turno", "numero", "partido_numero", "cod_tse", "zona_numero", "votos"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    if "nascimento" in df.columns:
        df["nascimento"] = pd.to_datetime(df["nascimento"], errors="coerce", format="%d/%m/%Y")
    df = df.dropna(subset=["sq_candidato", "ano"])
    return df


def split_candidatos_votacao(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cand_cols = [
        "ano", "turno", "cargo", "sq_candidato", "nome", "nome_urna",
        "numero", "partido_numero", "partido_sigla", "partido_nome",
        "coligacao", "situacao", "genero", "nascimento",
    ]
    cand_cols = [c for c in cand_cols if c in df.columns]
    candidatos = (
        df[cand_cols]
        .drop_duplicates(subset=["ano", "turno", "sq_candidato"])
        .copy()
    )
    candidatos["nome_normalizado"] = candidatos["nome"].apply(_norm)

    voto_cols = [c for c in
                 ("ano", "turno", "sq_candidato", "cod_tse", "municipio_nome",
                  "zona_numero", "votos") if c in df.columns]
    votacao = df[voto_cols].copy()
    votacao["votos"] = votacao["votos"].fillna(0).astype("Int64")
    votacao = (
        votacao.groupby(
            [c for c in voto_cols if c != "votos"],
            dropna=False,
            as_index=False,
        )["votos"].sum()
    )
    return candidatos, votacao


def main() -> int:
    todos_cand: list[pd.DataFrame] = []
    todas_vot: list[pd.DataFrame] = []
    for ano in ANOS:
        path = RAW_DIR / f"votacao_candidato_munzona_{UF}_{ano}.csv"
        if not path.exists():
            print(f"[normalize] AVISO: {path} não existe — execute tse_download primeiro.")
            continue
        df = carregar_csv(path)
        c, v = split_candidatos_votacao(df)
        todos_cand.append(c)
        todas_vot.append(v)

    if not todos_cand:
        print("[normalize] Nada para processar.", file=sys.stderr)
        return 1

    candidatos = pd.concat(todos_cand, ignore_index=True)
    votacoes = pd.concat(todas_vot, ignore_index=True)

    out_c = PROCESSED_DIR / "candidatos.parquet"
    out_v = PROCESSED_DIR / "votacoes.parquet"
    candidatos.to_parquet(out_c, index=False)
    votacoes.to_parquet(out_v, index=False)
    print(f"[normalize] {len(candidatos)} candidaturas -> {out_c}")
    print(f"[normalize] {len(votacoes)} linhas de votacao -> {out_v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
