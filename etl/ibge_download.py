"""
Baixa malha municipal do Acre via IBGE Servico de Dados.
Resultado: data/geo/municipios_AC.geojson + data/processed/municipios.parquet
"""
from __future__ import annotations

import json
import sys

import pandas as pd
import requests

from etl.config import GEO_DIR, PROCESSED_DIR, UF, UF_COD_IBGE

API_MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf_cod}"
API_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"


def baixar_geojson_municipios(uf: str = UF) -> dict:
    uf_cod = UF_COD_IBGE[uf]
    url = API_MALHA.format(uf_cod=uf_cod)
    params = {
        "formato": "application/vnd.geo+json",
        "qualidade": "intermediaria",
        "intrarregiao": "municipio",
    }
    print(f"[ibge] Baixando malha municipal {uf} ...")
    r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    out = GEO_DIR / f"municipios_{uf}.geojson"
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"[ibge] GeoJSON salvo em {out}")
    return data


def baixar_metadados_municipios(uf: str = UF) -> pd.DataFrame:
    url = API_MUNICIPIOS.format(uf=uf)
    print(f"[ibge] Baixando metadados de municipios {uf} ...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    rows = []
    for m in r.json():
        rows.append({
            "cod_ibge": int(m["id"]),
            "nome": m["nome"],
            "microrregiao": m.get("microrregiao", {}).get("nome"),
            "mesorregiao": m.get("microrregiao", {}).get("mesorregiao", {}).get("nome"),
        })
    df = pd.DataFrame(rows)
    out = PROCESSED_DIR / f"municipios_{uf}.parquet"
    df.to_parquet(out, index=False)
    print(f"[ibge] {len(df)} municipios salvos em {out}")
    return df


def main() -> int:
    baixar_geojson_municipios()
    baixar_metadados_municipios()
    return 0


if __name__ == "__main__":
    sys.exit(main())
