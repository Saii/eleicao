"""
Geocoda locais de votacao sem latitude/longitude usando Nominatim (OpenStreetMap).
Politica: rate limit 1 req/s (obrigatorio); user-agent identificavel.
"""
from __future__ import annotations

import sys
import time

import requests
from sqlalchemy import create_engine, text

from etl.config import DB_URL_SYNC

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "campanha-ac-etl/0.1 (xdiehunter@gmail.com)"


def geocodar(endereco: str, bairro: str | None, municipio: str, uf: str = "AC") -> tuple[float, float] | None:
    partes = [p for p in (endereco, bairro, municipio, uf, "Brasil") if p]
    q = ", ".join(partes)
    try:
        r = requests.get(
            NOMINATIM,
            params={"q": q, "format": "json", "limit": 1, "countrycodes": "br"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        r.raise_for_status()
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        print(f"  ! erro: {exc}")
    return None


def main() -> int:
    engine = create_engine(DB_URL_SYNC, future=True)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT lv.id, lv.nome, lv.endereco, lv.bairro, m.nome AS municipio
            FROM local_votacao lv
            LEFT JOIN municipio m ON m.cod_ibge = lv.municipio_cod
            WHERE lv.latitude IS NULL
        """)).mappings().all()

    if not rows:
        print("[geocode] Sem locais para geocodar.")
        return 0

    print(f"[geocode] {len(rows)} locais sem coords. Iniciando ...")
    encontrados = 0
    for r in rows:
        print(f"  - [{r['id']}] {r['nome']} / {r['municipio']}")
        coords = geocodar(r["endereco"], r["bairro"], r["municipio"])
        if coords:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE local_votacao
                        SET latitude = :lat, longitude = :lng, fonte_geo = 'nominatim'
                        WHERE id = :id
                    """),
                    {"lat": coords[0], "lng": coords[1], "id": r["id"]},
                )
            encontrados += 1
            print(f"    OK {coords[0]}, {coords[1]}")
        else:
            print("    sem resultado")
        time.sleep(1.0)  # rate limit OSM

    print(f"[geocode] OK · {encontrados}/{len(rows)} geocodados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
