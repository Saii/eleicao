-- ============================================================
-- Migration 004: Metas avançadas — decomposição, snapshots, projeção
-- ============================================================

-- Estende a tabela meta existente (mantém apoiadores_alvo, votos_alvo etc.)
ALTER TABLE meta
    ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'municipio',
    ADD COLUMN IF NOT EXISTS meta_pai_id UUID REFERENCES meta(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS candidatura_id UUID REFERENCES candidatura(id),
    ADD COLUMN IF NOT EXISTS cargo TEXT,                -- 'Deputado Federal'
    ADD COLUMN IF NOT EXISTS ano_alvo INTEGER,          -- 2026
    ADD COLUMN IF NOT EXISTS data_eleicao DATE;

-- tipo: estado | municipio | zona | secao | canal
-- meta-mãe (estado) tem meta_pai_id = NULL
-- filhas: tipo='municipio' apontam para meta-mãe

CREATE INDEX IF NOT EXISTS idx_meta_tipo ON meta(tipo);
CREATE INDEX IF NOT EXISTS idx_meta_pai ON meta(meta_pai_id);

-- Snapshot diário do progresso (para burndown / série temporal)
CREATE TABLE IF NOT EXISTS meta_snapshot (
    id BIGSERIAL PRIMARY KEY,
    meta_id UUID NOT NULL REFERENCES meta(id) ON DELETE CASCADE,
    data DATE NOT NULL,
    votos_projetados INTEGER NOT NULL DEFAULT 0,
    apoiadores_count INTEGER NOT NULL DEFAULT 0,
    pct_atingido NUMERIC(6, 2) NOT NULL DEFAULT 0,
    cenario TEXT NOT NULL DEFAULT 'realista',
    UNIQUE (meta_id, data, cenario)
);
CREATE INDEX IF NOT EXISTS idx_snapshot_meta ON meta_snapshot(meta_id, data);

-- Configurações de projeção (cenários nomeados)
CREATE TABLE IF NOT EXISTS projecao_config (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    descricao TEXT,
    m_nivel_1 NUMERIC(5, 2) NOT NULL DEFAULT 0.5,
    m_nivel_2 NUMERIC(5, 2) NOT NULL DEFAULT 1.5,
    m_nivel_3 NUMERIC(5, 2) NOT NULL DEFAULT 5.0,
    m_nivel_4 NUMERIC(5, 2) NOT NULL DEFAULT 30.0,
    fator_evento NUMERIC(4, 3) NOT NULL DEFAULT 0.20,
    decay_temporal NUMERIC(4, 3) NOT NULL DEFAULT 0.65,
    retencao_historica NUMERIC(4, 3) NOT NULL DEFAULT 0.85,
    ativo BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seeds: 2 cenários
INSERT INTO projecao_config (nome, descricao, m_nivel_1, m_nivel_2, m_nivel_3, m_nivel_4,
                             fator_evento, decay_temporal, retencao_historica, ativo)
VALUES
    ('realista',
     'Multiplicadores baseados em literatura de campanhas: leads valem pouco, militantes puxam rede pequena, lideranças têm capilaridade alta.',
     0.5, 1.5, 5.0, 30.0, 0.20, 0.65, 0.85, TRUE),
    ('conservador',
     'Hipótese cautelosa: assume baixa retenção e multiplicadores mais modestos.',
     1.0, 1.0, 3.0, 15.0, 0.10, 0.50, 0.70, FALSE)
ON CONFLICT (nome) DO NOTHING;
