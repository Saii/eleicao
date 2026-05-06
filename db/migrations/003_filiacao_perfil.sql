-- ============================================================
-- Migration 003: perfil agregado de filiação partidária (TSE não publica mais nominal por LGPD)
-- ============================================================

-- A tabela `filiado` da migration 002 fica sem uso por ora (reservada para
-- eventual fonte alternativa: Brasil.IO ou Base dos Dados com dados históricos).

CREATE TABLE IF NOT EXISTS filiacao_perfil (
    id              BIGSERIAL PRIMARY KEY,
    partido_numero  INTEGER REFERENCES partido(numero),
    municipio_cod   BIGINT REFERENCES municipio(cod_ibge),
    zona_numero     INTEGER,
    ds_genero       TEXT,
    ds_faixa_etaria TEXT,
    ds_estado_civil TEXT,
    ds_grau_instrucao TEXT,
    qt_filiado      INTEGER NOT NULL,
    nr_ano_mes      INTEGER NOT NULL,        -- referência YYYYMM do dump
    snapshot_em     DATE
);
CREATE INDEX IF NOT EXISTS idx_perfil_partido_municipio ON filiacao_perfil (partido_numero, municipio_cod);
CREATE INDEX IF NOT EXISTS idx_perfil_municipio ON filiacao_perfil (municipio_cod);

-- View agregada: total de filiados por partido x município
CREATE OR REPLACE VIEW v_filiados_municipio AS
SELECT fp.partido_numero,
       p.sigla AS partido_sigla,
       fp.municipio_cod,
       m.nome AS municipio_nome,
       SUM(fp.qt_filiado) AS qt_filiado,
       MAX(fp.nr_ano_mes) AS ref
FROM filiacao_perfil fp
LEFT JOIN partido p   ON p.numero    = fp.partido_numero
LEFT JOIN municipio m ON m.cod_ibge  = fp.municipio_cod
GROUP BY fp.partido_numero, p.sigla, fp.municipio_cod, m.nome;
