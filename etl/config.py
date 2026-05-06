from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GEO_DIR = DATA_DIR / "geo"

for d in (RAW_DIR, PROCESSED_DIR, GEO_DIR):
    d.mkdir(parents=True, exist_ok=True)

UF = os.getenv("ETL_UF", "AC")
ANOS = [int(a) for a in os.getenv("ETL_ANOS", "2020,2022,2024").split(",")]

DB_URL_SYNC = os.getenv(
    "DB_URL_SYNC",
    "postgresql://postgres:postgres@localhost:5432/campanha_ac",
)

# UF → código IBGE
UF_COD_IBGE = {
    "AC": 12, "AL": 27, "AM": 13, "AP": 16, "BA": 29, "CE": 23, "DF": 53,
    "ES": 32, "GO": 52, "MA": 21, "MG": 31, "MS": 50, "MT": 51, "PA": 15,
    "PB": 25, "PE": 26, "PI": 22, "PR": 41, "RJ": 33, "RN": 24, "RO": 11,
    "RR": 14, "RS": 43, "SC": 42, "SE": 28, "SP": 35, "TO": 17,
}
