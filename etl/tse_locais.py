"""
Baixa dados de eleitorado por local de votacao (TSE) — escolas/predios + endereco + lat/long.
URL: https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_<ano>.zip
(diretorio plural 'locais', arquivo singular)

CSV nacional unico — filtra por UF em streaming.
Saida: data/raw/eleitorado_local_votacao_<UF>_<ano>.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

from etl.config import RAW_DIR, UF

URL_TPL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/"
    "eleitorado_locais_votacao/eleitorado_local_votacao_{ano}.zip"
)


def baixar_zip(ano: int) -> Path:
    url = URL_TPL.format(ano=ano)
    out_zip = RAW_DIR / f"eleitorado_local_votacao_{ano}.zip"
    print(f"[locais] GET {url}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(out_zip, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=f"Locais {ano}") as bar:
            for chunk in r.iter_content(chunk_size=2**18):
                f.write(chunk)
                bar.update(len(chunk))
    return out_zip


def extrair_uf(zip_path: Path, uf: str, ano: int) -> Path:
    out_csv = RAW_DIR / f"eleitorado_local_votacao_{uf}_{ano}.csv"
    with zipfile.ZipFile(zip_path) as zf:
        nomes = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not nomes:
            raise RuntimeError(f"Nenhum CSV no ZIP: {zf.namelist()[:5]}")
        nome = nomes[0]
        print(f"[locais] Filtrando {nome} por UF={uf}")
        with zf.open(nome) as src:
            wrapper = io.TextIOWrapper(src, encoding="latin-1", newline="")
            reader = csv.reader(wrapper, delimiter=";")
            header = next(reader)
            try:
                idx_uf = header.index("SG_UF")
            except ValueError as exc:
                raise RuntimeError(f"SG_UF nao achado. Header: {header}") from exc
            with open(out_csv, "w", encoding="utf-8", newline="") as dst:
                writer = csv.writer(dst, delimiter=";")
                writer.writerow(header)
                kept = 0
                for row in reader:
                    if len(row) > idx_uf and row[idx_uf].strip().upper() == uf.upper():
                        writer.writerow(row)
                        kept += 1
        print(f"[locais] {kept} linhas salvas em {out_csv}")
    return out_csv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, default=2024)
    parser.add_argument("--uf", default=UF)
    args = parser.parse_args()
    zip_path = baixar_zip(args.ano)
    extrair_uf(zip_path, args.uf, args.ano)
    return 0


if __name__ == "__main__":
    sys.exit(main())
