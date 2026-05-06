"""
Baixa votos por secao do TSE.
URL: https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_<ano>.zip
Saida: data/raw/votacao_secao_<UF>_<ano>.csv

ZIP nacional contem CSVs por UF (ja vem segmentado).
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

from etl.config import RAW_DIR, UF

URL_TPL = "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_{ano}_{uf}.zip"


def baixar_zip(ano: int, uf: str) -> Path:
    url = URL_TPL.format(ano=ano, uf=uf.upper())
    out_zip = RAW_DIR / f"votacao_secao_{ano}.zip"
    print(f"[secao] GET {url}")
    with requests.get(url, stream=True, timeout=1800) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(out_zip, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=f"Secao {ano}") as bar:
            for chunk in r.iter_content(chunk_size=2**18):
                f.write(chunk)
                bar.update(len(chunk))
    return out_zip


def extrair_uf(zip_path: Path, uf: str, ano: int) -> Path:
    with zipfile.ZipFile(zip_path) as zf:
        nomes_csv = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        # Quando ZIP ja eh especifico da UF, basta pegar o primeiro CSV
        alvos = [n for n in nomes_csv if n.upper().endswith(f"_{uf.upper()}.CSV")] or nomes_csv
        if not alvos:
            raise RuntimeError(f"CSV nao encontrado. Conteudo: {zf.namelist()[:5]}")
        nome = alvos[0]
        out = RAW_DIR / f"votacao_secao_{uf}_{ano}.csv"
        with zf.open(nome) as src, open(out, "wb") as dst:
            dst.write(src.read())
        print(f"[secao] Extraido: {out}")
        return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, default=2024)
    parser.add_argument("--uf", default=UF)
    args = parser.parse_args()
    zip_path = baixar_zip(args.ano, args.uf)
    extrair_uf(zip_path, args.uf, args.ano)
    return 0


if __name__ == "__main__":
    sys.exit(main())
