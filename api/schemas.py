from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ---------- Eleitoral ----------

class Municipio(BaseModel):
    cod_ibge: int
    nome: str
    populacao: int | None = None


class Partido(BaseModel):
    numero: int
    sigla: str
    nome: str


class CandidatoBusca(BaseModel):
    candidatura_id: UUID
    candidato_id: UUID
    nome: str
    nome_urna: str | None
    ano: int
    cargo: str
    numero: int
    partido_sigla: str | None
    total_votos: int


class VotoZona(BaseModel):
    municipio_cod: int | None
    municipio_nome: str | None
    zona_numero: int
    votos: int


class CandidatoDetalhe(BaseModel):
    candidatura_id: UUID
    nome: str
    nome_urna: str | None
    ano: int
    cargo: str
    numero: int
    partido_sigla: str | None
    coligacao: str | None
    situacao: str | None
    total_votos: int
    por_zona: list[VotoZona]


# ---------- Auth ----------

class LoginIn(BaseModel):
    email: EmailStr
    senha: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioOut(BaseModel):
    id: UUID
    email: EmailStr
    nome: str
    papel: str
    ativo: bool


class UsuarioCreate(BaseModel):
    email: EmailStr
    nome: str
    senha: str = Field(min_length=8)
    papel: str = "membro"


# ---------- Campanha ----------

class ApoiadorIn(BaseModel):
    nome: str
    telefone: str | None = None
    email: EmailStr | None = None
    cpf: str | None = None
    titulo_eleitor: str | None = None
    municipio_cod: int | None = None
    zona_numero: int | None = None
    secao: int | None = None
    bairro: str | None = None
    endereco: str | None = None
    nivel_engajamento: int = 1
    observacoes: str | None = None


class ApoiadorOut(ApoiadorIn):
    id: UUID
    criado_em: datetime
    atualizado_em: datetime


class EventoIn(BaseModel):
    titulo: str
    descricao: str | None = None
    inicio: datetime
    fim: datetime | None = None
    local: str | None = None
    municipio_cod: int | None = None
    zona_numero: int | None = None
    bairro: str | None = None
    publico_estimado: int | None = None
    status: str = "planejado"


class EventoOut(EventoIn):
    id: UUID
    publico_real: int | None = None
    criado_em: datetime


class AnotacaoIn(BaseModel):
    titulo: str
    conteudo: str | None = None
    municipio_cod: int | None = None
    zona_numero: int | None = None
    bairro: str | None = None
    tags: list[str] = []


class AnotacaoOut(AnotacaoIn):
    id: UUID
    criado_em: datetime
    atualizado_em: datetime


class MetaIn(BaseModel):
    descricao: str
    municipio_cod: int | None = None
    zona_numero: int | None = None
    votos_alvo: int | None = None
    apoiadores_alvo: int | None = None
    prazo: date | None = None
    status: str = "aberta"


class MetaOut(MetaIn):
    id: UUID
    criado_em: datetime
