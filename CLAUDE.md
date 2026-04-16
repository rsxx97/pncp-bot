# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-project monorepo for Brazilian public procurement (licitacoes) automation. The system monitors government tenders (PNCP portal), analyzes them with AI, generates pricing spreadsheets, and provides competitive intelligence — all integrated with Telegram notifications and a web dashboard.

## Repository Structure

Three independent systems coexist at root level:

1. **Root-level bot** (`pncp_telegram_bot.py`, `app.py`, `database.py`) — Standalone PNCP monitor + Flask web dashboard. Uses `config.json` for filters, `licitacoes.db` (SQLite), sends alerts via Telegram. Runs hourly on GitHub Actions (`.github/workflows/pncp_bot.yml`).

2. **`licitacoes-ai/`** — Main AI-powered multi-agent system (FastAPI + React). This is the primary system under active development.

3. **`advanced-seguros/`** and **`real-outdoor-solutions/`** — Separate frontend projects (React/Vite and static HTML respectively). Not part of the licitacoes pipeline.

## licitacoes-ai Architecture

### 4-Agent Pipeline

Each agent corresponds to a stage in the tender analysis pipeline:

- **agente1_monitor** — Polls PNCP API, filters by keywords/state, scores relevance via LLM classification. Deduplicates against DB.
- **agente2_analista** — Downloads PDFs/spreadsheets, extracts requirements via LLM, analyzes Terms of Reference (work positions, CCT, benefits), ranks viable companies.
- **agente3_precificador** — Builds cost spreadsheets using IN 05/2017 model; calculates BDI, encargos (taxes/benefits), generates pricing scenarios with openpyxl.
- **agente4_competitivo** — Profiles competitors (win rates, aggression), analyzes bid history, suggests lance amounts.

Pipeline is sequential: monitor -> analista -> precificador -> competitivo.

### Key Subsystems

- **`api/`** — FastAPI backend with routes for dashboard, editais, pregoes, lances_robot, alertas, auth, config. Serves React SPA from `api/static/`.
- **`api/portais/`** — Multi-portal scrapers (PNCP, ComprasGov) with a manager pattern.
- **`bot_telegram/`** — Telegram bot interface (handlers, callbacks, keyboards) for interacting with the pipeline.
- **`dashboard/`** — Separate FastAPI app for KPI metrics.
- **`frontend/`** — React 19 + Vite dashboard. Built output goes to `api/static/`.
- **`chrome-extension/`** — Chrome MV3 extension that captures tender/bid data from 8 Brazilian procurement portals and sends to the API.
- **`shared/`** — Common modules: database (SQLite), LLM client (Anthropic/Gemini), telegram utils, models.
- **`config/settings.py`** — Central config loading from `.env` and environment variables.

### Database

Two separate SQLite databases:
- Root `licitacoes.db` — Used by the standalone bot (`database.py`). Tables: `oportunidades`, `comentarios`, `acompanhamentos`.
- `licitacoes-ai/data/licitacoes.db` — Used by the AI system (`shared/database.py`). Main table: `editais` with columns for each agent's output (score, analise_json, planilha_path, analise_competitiva_json).

Both use WAL mode and thread-local connections.

## Commands

### Root-level bot
```bash
python pncp_telegram_bot.py                    # Run PNCP monitor
python pncp_telegram_bot.py --config config_cloud.json  # With alternate config
python app.py                                  # Flask dashboard on :5000
python emop_scraper.py                         # EMOP-RJ scraper
```

### licitacoes-ai system
```bash
cd licitacoes-ai
python run.py tudo              # Start everything (dashboard + bot + scheduler)
python run.py dashboard         # FastAPI dashboard only on :8000
python run.py bot               # Telegram bot only
python run.py monitor           # Run monitor once
python run.py pipeline --pncp-id <ID>  # Run full pipeline for one tender
python start.py                 # Alternative: API server + monitor + bot (for Railway)
```

### Frontend
```bash
cd licitacoes-ai/frontend
npm install
npm run dev      # Vite dev server
npm run build    # Build to ../api/static/
```

## Environment Variables

The AI system (`licitacoes-ai/.env`) requires:
- `ANTHROPIC_API_KEY` — Claude API (used for analysis, classification, pricing)
- `GEMINI_API_KEY` — Google Gemini (alternative LLM)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Telegram integration
- `ESTADO_FOCO` — Target state (default: "RJ")
- `CLAUDE_MODEL` — Model for LLM calls (default: `claude-haiku-4-20250414`)

The standalone bot uses `config.json` with Telegram credentials and filter keywords.

## Deployment

- **Railway** — `licitacoes-ai/Dockerfile` (Python 3.11-slim), persists `/app/data` volume. Health check at `/api/health`.
- **GitHub Actions** — Root bot runs hourly Mon-Fri 10h-23h UTC via `pncp_bot.yml`. Uses artifact caching for `enviados.json` and `licitacoes.db`.

## Language

All code, comments, variable names, and UI text are in **Brazilian Portuguese**. Maintain this convention.