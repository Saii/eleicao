# Deploy — Campanha AC

Guia para publicar online usando **Streamlit Cloud + Supabase + Render** (tudo grátis).

## Pré-requisitos

- Conta GitHub (você já tem)
- Banco local com dados populados (já está)
- 30 minutos

## A. GitHub — repo público novo

1. Acesse https://github.com/new
2. Nome: `campanha-ac` · **Public** · sem README/license
3. Não inicialize, deixe vazio
4. Clique "Create repository"
5. Copie a URL HTTPS (ex: `https://github.com/seu-user/campanha-ac.git`) e me envie

Vou rodar `git init`, commit e push.

## B. Supabase — banco de dados

1. https://supabase.com → Sign in com GitHub
2. **New project**:
   - Name: `campanha-ac`
   - Database password: **gere uma senha forte e SALVE** (vamos usar)
   - Region: `South America (São Paulo)` (sa-east-1)
   - Plan: Free
3. Aguarde ~2 min provisionar
4. **Settings → Database → Connection string → URI** → copie e me envie. Formato:
   `postgresql://postgres.[ref]:[senha]@[host]:5432/postgres`

Eu faço:
- Aplico schema + migrations: `python -m scripts.run_migrations` (com `DB_URL_SYNC=...` apontando para Supabase)
- Exporto dump local: `.\scripts\export_dump.ps1`
- Importo no Supabase: `psql "<connection>" -f dump_data.sql`
- Crio admin em prod: `python -m scripts.create_admin_prod --db-url "<connection>"`

## C. Render — API FastAPI

1. https://render.com → Sign in com GitHub
2. **New → Web Service** → conectar o repo `campanha-ac`
3. Render detecta `render.yaml`. Clique "Apply"
4. Configure as variáveis (painel **Environment**):
   - `DB_URL` = connection string do Supabase com prefixo `postgresql+psycopg://` (substitua `postgresql://` no início)
   - `JWT_SECRET` = deixe gerar automático
   - `API_CORS_ORIGINS` = `*` (vamos apertar depois)
5. Aguarde build (~5 min)
6. URL gerada: `https://campanha-ac-api.onrender.com`. Teste: `https://...onrender.com/health`

## D. Streamlit Cloud — Frontend

1. https://share.streamlit.io → Sign in com GitHub
2. **New app**:
   - Repository: `seu-user/campanha-ac`
   - Branch: `main`
   - Main file path: `dashboard/app.py`
3. **Advanced settings → Secrets**:
   ```
   DASH_API_BASE = "https://campanha-ac-api.onrender.com"
   ```
4. Deploy → URL gerada: `https://campanha-ac-xxxx.streamlit.app`

## E. Apertar CORS

1. No Render → Environment → atualize:
   `API_CORS_ORIGINS` = `https://campanha-ac-xxxx.streamlit.app` (URL real do passo D)
2. Aguarde redeploy automático

## F. Smoke test

1. Abra a URL Streamlit → tela de login
2. Entre com email/senha do admin (criado no passo B)
3. Navegue: Mapa, Rueda (todas as abas), Apoiadores, Metas
4. Tudo OK → deploy concluído

## Manutenção

- **Render free dorme após 15 min**. 1ª request leva 30-60s. Para evitar: cron-job.org → ping `/health` a cada 14 min.
- **Supabase pausa após 7 dias inativo**. Acesse 1×/semana ou faça backup com `pg_dump`.
- **Atualizações**: `git push` → Render e Streamlit redeploy automático.
- **Logs**: Render dashboard → Logs · Streamlit → Manage app → Logs.

## Custos (grátis)

| Serviço | Limite free | Uso atual |
|---|---|---|
| GitHub | ilimitado public | OK |
| Supabase | 500 MB DB · 5 GB egress/mês | 96 MB · pouco egress |
| Render | 750h/mês web service | OK |
| Streamlit Cloud | 1 app público | OK |

Total: **R$ 0/mês** com cold starts toleráveis.
