"""
Baixa CSVs de votação do TSE (Dados Abertos) para uma UF e ano.
Arquivo: votacao_candidato_munzona_<ANO>.zip → CSV por UF dentro.

URL padrão (estável desde ~2018):
  https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_{ANO}.zip

Saída: data/raw/votacao_candidato_munzona_{UF}_{ANO}.csv
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

from etl.config import ANOS, RAW_DIR, UF

URL_TPL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/"
    "votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip"
)


def baixar_zip(ano: int) -> bytes:
    url = URL_TPL.format(ano=ano)
    print(f"[tse] GET {url}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        buf = io.BytesIO()
        with tqdm(total=total, unit="B", unit_scale=True, desc=f"TSE {ano}") as bar:
            for chunk in r.iter_content(chunk_size=2**16):
                buf.write(chunk)
                bar.update(len(chunk))
        return buf.getvalue()


def extrair_uf(zip_bytes: bytes, uf: str, ano: int) -> Path:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # nomes típicos: votacao_candidato_munzona_2024_AC.csv
        alvos = [
            n for n in zf.namelist()
            if n.upper().endswith(f"_{uf.upper()}.CSV")
        ]
        if not alvos:
            raise RuntimeError(f"CSV da UF {uf} não encontrado no ZIP de {ano}. Conteúdo: {zf.namelist()[:5]}")
        nome = alvos[0]
        out = RAW_DIR / f"votacao_candidato_munzona_{uf}_{ano}.csv"
        with zf.open(nome) as src, open(out, "wb") as dst:
            dst.write(src.read())
        print(f"[tse] Extraído: {out}")
        return out


def baixar_ano(ano: int, uf: str = UF) -> Path:
    zip_bytes = baixar_zip(ano)
    return extrair_uf(zip_bytes, uf, ano)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, action="append",
                        help="Ano da eleição (pode repetir). Default: ETL_ANOS do .env")
    parser.add_argument("--uf", default=UF)
    args = parser.parse_args()

    anos = args.ano or ANOS
    for ano in anos:
        try:
            baixar_ano(ano, args.uf)
        except Exception as e:
            print(f"[tse] Falha ano {ano}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
