# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-project monorepo for Brazilian public procurement (licitacoes) automation. The system monitors government tenders (PNCP portal + other state portals), analyzes them with AI, generates pricing spreadsheets, and provides competitive intelligence — all integrated with Telegram notifications and a web dashboard.

## Repository Structure

Three independent systems coexist at the root:

1. **Root-level bot** (`pncp_telegram_bot.py`, `app.py`, `database.py`, `emop_scraper.py`, `templates/`) — Standalone PNCP monitor + Flask web dashboard (`app.py` on :5000). Uses `config.json` (gitignored — populated from `CONFIG_JSON` GitHub secret as `config_cloud.json` in CI) for filters, `licitacoes.db` (SQLite). Runs hourly on GitHub Actions.

2. **`licitacoes-ai/`** — Main AI-powered multi-agent system (FastAPI + React). Primary system under active development.

3. **`advanced-seguros/`** (React/Vite) and **`gbgroup/`** (static HTML/CSS/JS) — Unrelated frontend projects for other businesses. Not part of the licitacoes pipeline. (`real-outdoor-solutions/` is gitignored.)

## licitacoes-ai Architecture

### 4-Agent Pipeline

Each agent is a separate Python package (`agente{1..4}_*`) corresponding to a stage:

- **`agente1_monitor`** — Polls PNCP API (`pncp_client.py`), filters by UF/keywords, classifies relevance via LLM (`classifier.py`), runs on a schedule (`scheduler.py`). Deduplicates against the `editais` table.
- **`agente2_analista`** — Downloads PDFs (`pdf_extractor.py`), extracts Edital + Termo de Referência data via Claude, producing structured JSON: postos de trabalho, CCT/sindicato, pisos salariais, benefícios (VA/VT/BSF), SAT/RAT, ISS, riscos.
- **`agente3_precificador`** — Builds cost spreadsheets (IN 05/2017 model) with openpyxl; computes BDI, encargos sociais, benefícios, generates pricing scenarios.
- **`agente4_competitivo`** — Searches PNCP historical results, ranks competitors (win rate, aggression), suggests lance amounts.

Pipeline is sequential: `monitor -> analista -> precificador -> competitivo`. The full pipeline for a single tender can be run via `python run.py pipeline --pncp-id <ID>`.

### Key Subsystems

- **`api/main.py`** — FastAPI app (`api.main:app`). Mounts all routers under `api/routes/` (dashboard, editais, pregoes, lances_robot, alertas, auth, config, concorrentes, perfil, planilhas, habilitacao, chat). Serves React SPA from `api/static/` with 404 → `index.html` fallback for client-side routing. CORS is permissive (`allow_origins=["*"]`).
- **`api/portais/`** — Multi-portal scrapers with a `manager.py` orchestrator (`base.py` ABC, `pncp.py`, `comprasgov.py`, `comprasgov_scraper.py`).
- **`bot_telegram/`** — Telegram bot (`main.py` entry, `handlers.py`, `callbacks.py`, `keyboards.py`). There is also a legacy `bot/` directory — prefer `bot_telegram/`.
- **`dashboard/api.py`** — Separate FastAPI app used by `run.py dashboard` for KPI metrics (port 8000). Different app than `api/main.py` (port 8001) — don't confuse them.
- **`frontend/`** — React 19 + Vite 8 + recharts. Dev server proxies `/api` to `localhost:8000`. Build output goes to `../api/static/` (configured in `vite.config.js`).
- **`chrome-extension/`** — Chrome MV3 extension that scrapes 8 Brazilian procurement portals (ComprasNet, compras.gov.br, compras.rj.gov.br, siga.rj, fazenda.rj, licitacoes-e BB, BLL, portaldecompraspublicas) and POSTs data to the deployed Railway API.
- **`shared/`** — `database.py` (SQLite, WAL, thread-local), `llm_client.py` (Anthropic/Gemini with token cost tracking), `telegram_utils.py`, `models.py`, `utils.py`.
- **`config/settings.py`** — Central config. Loads `.env` via `python-dotenv`, defines `KEYWORDS_INTERESSE` / `KEYWORDS_EXCLUSAO` lists, `CNAES_GRUPO` (per-company CNAEs for manutec/blue/miami), `UFS_FOCO`, `CLAUDE_PRICING`. Edit this file when changing business rules, not `.env`.
- **`config/*.json`** — Runtime config: `concorrentes.json`, `empresa_perfil.json`, `mdo_padrao.json` (default mão-de-obra template).

### Two entry points, different runtimes

- **`run.py`** — Dev/local. Subcommands: `dashboard` (port 8000, serves `dashboard.api:app`), `bot`, `monitor` (one-shot), `pipeline --pncp-id <ID>`, `tudo` (scheduler thread + bot thread + dashboard foreground).
- **`start.py`** — Production (Railway, `Dockerfile` `CMD`). Starts `api.main:app` on `$PORT` (default **8001**), plus monitor-loop thread (no APScheduler — bare `while True: sleep(INTERVALO)`) and bot thread. `usar_llm=False, incluir_nacional=False` in the monitor loop to save API costs.

### Database

Two separate SQLite databases — don't cross them:
- **Root `licitacoes.db`** — Standalone bot (`database.py`). Tables: `oportunidades`, `comentarios`, `acompanhamentos`.
- **`licitacoes-ai/data/licitacoes.db`** — AI system (`shared/database.py`). Primary table `editais` has per-agent output columns (`score`, `analise_json`, `planilha_path`, `analise_competitiva_json`). Also pregoes, lances, alertas, perfil tables.

Both use WAL mode and thread-local connections. The `data/` volume is mounted at `/app/data` on Railway (persisted across deploys).

## Commands

### Root-level bot
```bash
pip install -r requirements.txt                         # just `requests`
python pncp_telegram_bot.py                             # Run once (uses config.json)
python pncp_telegram_bot.py --config config_cloud.json  # Alternate config (used in CI)
python app.py                                           # Flask dashboard on :5000
python emop_scraper.py                                  # EMOP-RJ scraper (one-off)
```

### licitacoes-ai system
```bash
cd licitacoes-ai
pip install -r requirements.txt

python run.py tudo                     # Dev: dashboard(:8000) + bot + scheduler
python run.py dashboard                # FastAPI dashboard only on :8000
python run.py bot                      # Telegram bot only
python run.py monitor                  # Run monitor once (uses LLM classifier)
python run.py pipeline --pncp-id <ID>  # Full pipeline for one tender

python start.py                        # Prod: api.main:app on :8001 + monitor loop + bot
python test_analise.py                 # Smoke-test agente2 against a sample PDF in data/editais
python search_pncp_matches.py          # Ad-hoc PNCP search
python insert_calendario.py            # Seed calendar data
```

There is no formal test suite or linter configured. `test_analise.py` is a smoke test, not pytest.

### Frontend
```bash
cd licitacoes-ai/frontend
npm install
npm run dev      # Vite dev server (proxies /api → :8000)
npm run build    # Emits to ../api/static/ — required before serving SPA in production
npm run preview  # Preview the production build
```

## Environment Variables

`licitacoes-ai/.env` (see `.env.example`):
- `ANTHROPIC_API_KEY` — Claude API (analysis, classification, pricing). Required.
- `GEMINI_API_KEY` — optional fallback LLM.
- `CLAUDE_MODEL` — default `claude-haiku-4-20250414` in `settings.py`; `.env.example` suggests `claude-sonnet-4-20250514` for better quality.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — if unset, the bot silently disables itself.
- `ESTADO_FOCO` (default `RJ`), `UFS_FOCO` (comma-separated, falls back to `ESTADO_FOCO`).
- `SCORE_MINIMO` (default 60), `INTERVALO_MONITOR_MINUTOS` (default 30), `MONITOR_INTERVALO_MIN` (used by `start.py`, default 30).
- `PORT` — honored by `start.py` (default 8001).

The standalone root bot uses `config.json` with Telegram credentials and filter keywords (provided via `CONFIG_JSON` GitHub secret in CI).

## Deployment

- **Railway** — `licitacoes-ai/Dockerfile` (Python 3.11-slim, `CMD ["python", "start.py"]`). `railway.toml` mounts `/app/data` and sets health check `/api/health` with a 300s timeout. The chrome-extension manifest hardcodes the Railway URL (`pncp-bot-production.up.railway.app`) as an allowed host.
- **GitHub Actions** — `.github/workflows/pncp_bot.yml` runs the root bot hourly Mon–Fri, 10h–23h UTC (≈7h–20h Brasília). Uploads/downloads a `pncp-cache` artifact containing `enviados.json` and `licitacoes.db` for state continuity.

## Conventions

- **Language**: all code, comments, variable names, log messages, and UI text are in **Brazilian Portuguese**. Maintain this — mixing English and Portuguese is jarring in this codebase.
- **No linter/formatter enforced**. Match the surrounding style (4-space indent, snake_case, type hints where present).
- When adding new API routes, register the router in `api/main.py`'s `include_router` block.
- When adding LLM calls, go through `shared/llm_client.ask_claude` (it handles token accounting via `CLAUDE_PRICING`), not raw `anthropic` SDK calls.
- New environment knobs belong in `config/settings.py` (and `.env.example`), not scattered `os.getenv` calls.
