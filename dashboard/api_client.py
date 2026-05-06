"""Cliente HTTP simples para a API FastAPI, com cache e auth via session_state."""
from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_BASE = os.getenv("DASH_API_BASE", "http://localhost:8000")


def _headers() -> dict:
    h = {"Accept": "application/json"}
    tok = st.session_state.get("token")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


@st.cache_data(ttl=60)
def get(path: str, params: dict | None = None) -> Any:
    r = httpx.get(f"{API_BASE}{path}", params=params, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def post(path: str, body: dict) -> Any:
    r = httpx.post(f"{API_BASE}{path}", json=body, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def login(email: str, senha: str) -> bool:
    r = httpx.post(f"{API_BASE}/auth/login", json={"email": email, "senha": senha}, timeout=30)
    if r.status_code != 200:
        return False
    st.session_state["token"] = r.json()["access_token"]
    return True


def logout() -> None:
    st.session_state.pop("token", None)
    st.cache_data.clear()


def autenticado() -> bool:
    return bool(st.session_state.get("token"))
