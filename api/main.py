from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.routes import (
    analise_partidaria,
    auth,
    campanha,
    candidatos,
    locais,
    mapa,
    metas,
    partidos,
    secoes,
    zonas,
)

app = FastAPI(
    title="Campanha AC API",
    description="Análise eleitoral do Acre + gestão de campanha (foco Fábio Rueda).",
    version="0.1.0",
)

# CORS: aceita lista por vírgula OU "*" (wildcard total) OU regex via prefixo "regex:"
_origins_raw = settings.API_CORS_ORIGINS.strip()
_cors_kwargs: dict = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if _origins_raw == "*":
    _cors_kwargs["allow_origins"] = ["*"]
    _cors_kwargs["allow_credentials"] = False  # wildcard exige sem credenciais
elif _origins_raw.startswith("regex:"):
    _cors_kwargs["allow_origin_regex"] = _origins_raw[len("regex:"):]
    _cors_kwargs["allow_origins"] = []
else:
    _cors_kwargs["allow_origins"] = [o.strip() for o in _origins_raw.split(",") if o.strip()]

app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(candidatos.router)
app.include_router(partidos.router)
app.include_router(zonas.router)
app.include_router(mapa.router)
app.include_router(locais.router)
app.include_router(secoes.router)
app.include_router(campanha.router)
app.include_router(metas.router)
app.include_router(analise_partidaria.router)
