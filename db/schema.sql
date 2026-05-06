-- ============================================================
-- Schema: Campanha AC (eleição + gestão)
-- Postgres 14+ com PostGIS
-- ============================================================

-- PostGIS é opcional. Por padrão usamos JSONB para a geometria (GeoJSON).
-- Se quiser PostGIS depois: instale via Stack Builder e altere `geom JSONB` para `geom GEOMETRY(MultiPolygon, 4674)`.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- DOMÍNIO ELEITORAL
-- ============================================================

CREATE TABLE IF NOT EXISTS municipio (
    cod_ibge        BIGINT PRIMARY KEY,
    cod_tse         INTEGER UNIQUE,
    nome            TEXT NOT NULL,
    nome_normalizado TEXT NOT NULL,
    populacao       INTEGER,
    geom            JSONB
);
CREATE INDEX IF NOT EXISTS idx_municipio_nome_trgm ON municipio USING GIN (nome_normalizado gin_trgm_ops);

CREATE TABLE IF NOT EXISTS zona_eleitoral (
    id              SERIAL PRIMARY KEY,
    numero          INTEGER NOT NULL,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    sede            TEXT,
    UNIQUE (numero)
);
CREATE INDEX IF NOT EXISTS idx_zona_municipio ON zona_eleitoral(municipio_cod);

CREATE TABLE IF NOT EXISTS partido (
    numero          INTEGER PRIMARY KEY,
    sigla           TEXT NOT NULL UNIQUE,
    nome            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidato (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sq_candidato    TEXT,
    cpf_hash        TEXT,
    nome            TEXT NOT NULL,
    nome_normalizado TEXT NOT NULL,
    nome_urna       TEXT,
    nascimento      DATE,
    genero          TEXT,
    UNIQUE (sq_candidato)
);
CREATE INDEX IF NOT EXISTS idx_candidato_nome_trgm ON candidato USING GIN (nome_normalizado gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_candidato_urna ON candidato (nome_urna);

CREATE TABLE IF NOT EXISTS candidatura (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidato_id    UUID NOT NULL REFERENCES candidato(id) ON DELETE CASCADE,
    ano             INTEGER NOT NULL,
    turno           SMALLINT NOT NULL DEFAULT 1,
    cargo           TEXT NOT NULL,           -- VEREADOR, PREFEITO, DEPUTADO ESTADUAL, ...
    numero          INTEGER NOT NULL,
    partido_numero  INTEGER REFERENCES partido(numero),
    coligacao       TEXT,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),  -- NULL se cargo estadual/federal
    situacao        TEXT,                    -- ELEITO, NÃO ELEITO, SUPLENTE, ...
    total_votos     INTEGER DEFAULT 0,
    UNIQUE (ano, turno, cargo, candidato_id)
);
CREATE INDEX IF NOT EXISTS idx_candidatura_busca ON candidatura (ano, cargo, partido_numero);
CREATE INDEX IF NOT EXISTS idx_candidatura_municipio ON candidatura (municipio_cod);

CREATE TABLE IF NOT EXISTS votacao (
    id              BIGSERIAL PRIMARY KEY,
    candidatura_id  UUID NOT NULL REFERENCES candidatura(id) ON DELETE CASCADE,
    zona_numero     INTEGER NOT NULL,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    votos           INTEGER NOT NULL,
    UNIQUE (candidatura_id, zona_numero, municipio_cod)
);
CREATE INDEX IF NOT EXISTS idx_votacao_candidatura ON votacao (candidatura_id);
CREATE INDEX IF NOT EXISTS idx_votacao_zona ON votacao (zona_numero);
CREATE INDEX IF NOT EXISTS idx_votacao_municipio ON votacao (municipio_cod);

-- View prática: votos agregados por município com nome do candidato e partido
CREATE OR REPLACE VIEW v_votos_municipio AS
SELECT
    cd.id            AS candidatura_id,
    cd.ano, cd.turno, cd.cargo, cd.numero,
    c.id             AS candidato_id,
    c.nome           AS candidato_nome,
    c.nome_urna,
    p.sigla          AS partido_sigla,
    p.numero         AS partido_numero,
    v.municipio_cod,
    m.nome           AS municipio_nome,
    SUM(v.votos)     AS votos
FROM votacao v
JOIN candidatura cd ON cd.id = v.candidatura_id
JOIN candidato   c  ON c.id  = cd.candidato_id
LEFT JOIN partido p ON p.numero = cd.partido_numero
LEFT JOIN municipio m ON m.cod_ibge = v.municipio_cod
GROUP BY cd.id, c.id, p.sigla, p.numero, v.municipio_cod, m.nome;

-- ============================================================
-- DOMÍNIO CAMPANHA / GESTÃO
-- ============================================================

CREATE TABLE IF NOT EXISTS usuario (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    nome            TEXT NOT NULL,
    senha_hash      TEXT NOT NULL,
    papel           TEXT NOT NULL DEFAULT 'membro',  -- admin, coordenador, membro
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS apoiador (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome            TEXT NOT NULL,
    telefone        TEXT,
    email           TEXT,
    cpf             TEXT UNIQUE,
    titulo_eleitor  TEXT,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    zona_numero     INTEGER,
    secao           INTEGER,
    bairro          TEXT,
    endereco        TEXT,
    nivel_engajamento SMALLINT DEFAULT 1,    -- 1=lead, 2=apoiador, 3=militante, 4=liderança
    observacoes     TEXT,
    cadastrado_por  UUID REFERENCES usuario(id),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_apoiador_municipio ON apoiador (municipio_cod);
CREATE INDEX IF NOT EXISTS idx_apoiador_zona ON apoiador (zona_numero);
CREATE INDEX IF NOT EXISTS idx_apoiador_nome_trgm ON apoiador USING GIN (nome gin_trgm_ops);

CREATE TABLE IF NOT EXISTS evento (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo          TEXT NOT NULL,
    descricao       TEXT,
    inicio          TIMESTAMPTZ NOT NULL,
    fim             TIMESTAMPTZ,
    local           TEXT,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    zona_numero     INTEGER,
    bairro          TEXT,
    publico_estimado INTEGER,
    publico_real    INTEGER,
    status          TEXT NOT NULL DEFAULT 'planejado', -- planejado, confirmado, realizado, cancelado
    criado_por      UUID REFERENCES usuario(id),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evento_inicio ON evento (inicio);
CREATE INDEX IF NOT EXISTS idx_evento_municipio ON evento (municipio_cod);

CREATE TABLE IF NOT EXISTS anotacao (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo          TEXT NOT NULL,
    conteudo        TEXT,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    zona_numero     INTEGER,
    bairro          TEXT,
    tags            TEXT[],
    criado_por      UUID REFERENCES usuario(id),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_anotacao_zona ON anotacao (zona_numero);
CREATE INDEX IF NOT EXISTS idx_anotacao_municipio ON anotacao (municipio_cod);
CREATE INDEX IF NOT EXISTS idx_anotacao_tags ON anotacao USING GIN (tags);

CREATE TABLE IF NOT EXISTS meta (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    descricao       TEXT NOT NULL,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    zona_numero     INTEGER,
    votos_alvo      INTEGER,
    apoiadores_alvo INTEGER,
    prazo           DATE,
    responsavel     UUID REFERENCES usuario(id),
    status          TEXT NOT NULL DEFAULT 'aberta',  -- aberta, em_andamento, atingida, perdida
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_meta_municipio ON meta (municipio_cod);

-- Trigger de atualizado_em
CREATE OR REPLACE FUNCTION trg_set_atualizado_em()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_apoiador_atualizado ON apoiador;
CREATE TRIGGER trg_apoiador_atualizado
BEFORE UPDATE ON apoiador
FOR EACH ROW EXECUTE FUNCTION trg_set_atualizado_em();

DROP TRIGGER IF EXISTS trg_anotacao_atualizado ON anotacao;
CREATE TRIGGER trg_anotacao_atualizado
BEFORE UPDATE ON anotacao
FOR EACH ROW EXECUTE FUNCTION trg_set_atualizado_em();
