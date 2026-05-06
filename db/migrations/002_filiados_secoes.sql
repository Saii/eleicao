-- ============================================================
-- Migration 002: filiados + seções/locais de votação
-- ============================================================

-- Filiados ao partido (snapshot TSE)
CREATE TABLE IF NOT EXISTS filiado (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nr_filiado      TEXT,
    nome            TEXT NOT NULL,
    nome_normalizado TEXT NOT NULL,
    titulo_eleitor  TEXT,
    partido_numero  INTEGER REFERENCES partido(numero),
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    zona_numero     INTEGER,
    secao_numero    INTEGER,
    data_filiacao   DATE,
    situacao        TEXT,
    snapshot_em     DATE,
    candidato_id    UUID REFERENCES candidato(id),
    UNIQUE (partido_numero, nr_filiado, snapshot_em)
);
CREATE INDEX IF NOT EXISTS idx_filiado_partido ON filiado (partido_numero);
CREATE INDEX IF NOT EXISTS idx_filiado_municipio ON filiado (municipio_cod);
CREATE INDEX IF NOT EXISTS idx_filiado_nome_trgm ON filiado USING GIN (nome_normalizado gin_trgm_ops);

-- Local de votação (escola/prédio)
CREATE TABLE IF NOT EXISTS local_votacao (
    id              SERIAL PRIMARY KEY,
    nr_local        INTEGER NOT NULL,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    zona_numero     INTEGER NOT NULL,
    nome            TEXT,
    endereco        TEXT,
    bairro          TEXT,
    cep             TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    fonte_geo       TEXT,
    UNIQUE (zona_numero, nr_local, municipio_cod)
);
CREATE INDEX IF NOT EXISTS idx_local_municipio ON local_votacao (municipio_cod);

-- Seção
CREATE TABLE IF NOT EXISTS secao_eleitoral (
    id              BIGSERIAL PRIMARY KEY,
    zona_numero     INTEGER NOT NULL,
    nr_secao        INTEGER NOT NULL,
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    local_id        INTEGER REFERENCES local_votacao(id),
    UNIQUE (zona_numero, nr_secao)
);
CREATE INDEX IF NOT EXISTS idx_secao_local ON secao_eleitoral (local_id);

-- Votação granular por seção
CREATE TABLE IF NOT EXISTS votacao_secao (
    candidatura_id  UUID NOT NULL REFERENCES candidatura(id) ON DELETE CASCADE,
    secao_id        BIGINT NOT NULL REFERENCES secao_eleitoral(id) ON DELETE CASCADE,
    votos           INTEGER NOT NULL,
    PRIMARY KEY (candidatura_id, secao_id)
);
CREATE INDEX IF NOT EXISTS idx_votsec_secao ON votacao_secao (secao_id);

CREATE OR REPLACE VIEW v_votos_local AS
SELECT vs.candidatura_id, lv.id AS local_id, lv.nome,
       lv.latitude, lv.longitude, lv.municipio_cod,
       SUM(vs.votos) AS votos
FROM votacao_secao vs
JOIN secao_eleitoral se ON se.id = vs.secao_id
JOIN local_votacao lv ON lv.id = se.local_id
GROUP BY vs.candidatura_id, lv.id;
