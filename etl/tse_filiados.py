"""
Baixa o dump de PERFIL de filiacao partidaria do TSE (agregado).
TSE descontinuou o dump nominal por LGPD em 2024 — agora so ha agregados
demograficos por (partido, municipio, zona, perfil), sem nomes.

URL: https://cdn.tse.jus.br/estatistica/sead/odsele/filiacao_partidaria/perfil_filiacao_partidaria.zip
Tamanho: ~230MB compactado / ~3.5GB descompactado (nacional)
Saida: data/raw/perfil_filiacao_<UF>.csv (filtrado por UF para reduzir volume)
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

URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/filiacao_partidaria/perfil_filiacao_partidaria.zip"


def baixar_zip() -> Path:
    """Baixa o zip nacional pra disco e retorna o path (evita carregar 3.5GB em memoria)."""
    out_zip = RAW_DIR / "perfil_filiacao_partidaria.zip"
    print(f"[filiados] GET {URL}")
    with requests.get(URL, stream=True, timeout=1800) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(out_zip, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc="Perfil filiacao") as bar:
            for chunk in r.iter_content(chunk_size=2**18):
                f.write(chunk)
                bar.update(len(chunk))
    return out_zip


def extrair_filtrado(zip_path: Path, uf: str) -> Path:
    """Le o CSV de dentro do ZIP em streaming e grava so as linhas de UF."""
    out_csv = RAW_DIR / f"perfil_filiacao_{uf.upper()}.csv"
    with zipfile.ZipFile(zip_path) as zf:
        nomes = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not nomes:
            raise RuntimeError(f"Nenhum CSV no ZIP: {zf.namelist()[:5]}")
        nome = nomes[0]
        print(f"[filiados] Filtrando {nome} por UF={uf} ...")
        with zf.open(nome) as src:
            wrapper = io.TextIOWrapper(src, encoding="latin-1", newline="")
            reader = csv.reader(wrapper, delimiter=";")
            header = next(reader)
            try:
                idx_uf = header.index("SG_UF")
            except ValueError as exc:
                raise RuntimeError(f"Coluna SG_UF nao encontrada. Header: {header}") from exc
            with open(out_csv, "w", encoding="utf-8", newline="") as dst:
                writer = csv.writer(dst, delimiter=";")
                writer.writerow(header)
                kept = 0
                for row in reader:
                    if len(row) > idx_uf and row[idx_uf].strip().upper() == uf.upper():
                        writer.writerow(row)
                        kept += 1
        print(f"[filiados] {kept} linhas salvas em {out_csv}")
    return out_csv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default=UF)
    parser.add_argument("--zip", help="Caminho de zip ja baixado (pula download)")
    args = parser.parse_args()
    zip_path = Path(args.zip) if args.zip else baixar_zip()
    extrair_filtrado(zip_path, args.uf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
