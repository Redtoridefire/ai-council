# AI Council System

Multi-agent AI decision engine using Claude, OpenAI, Gemini, and local model routing.

## Features
- Parallel multi-agent reasoning
- Red team logic + cyber analysis
- Debate and critique phases
- Chairman synthesis decision
- Evidence injection (RAG) from `docs/`
- Weighted council voting (`confidence` + `risk_score` aggregation)
- SQLite-backed council memory for previous decisions
- Telegram bot interface (`/council <question>`)
- Local model support via Ollama-compatible HTTP endpoint
- Streamlit dashboard for confidence/risk/disagreement trends
- Expanded council roles (Cloud Architect, Threat Intelligence Analyst, Compliance Officer, AI Safety Officer)
- Built-in provider rate limiting and telemetry event logging
- Prompt/log redaction helpers for basic secret hygiene

## Railway deployment (optimized)
This repo is configured for smaller Railway builds:
- `requirements.txt` is **core runtime only** (Telegram + council engine)
- `requirements-dashboard.txt` is optional local dashboard tooling
- `railway.json` sets build and start commands for Telegram hosting

### Required Railway env vars
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`

### Optional Railway env vars
- `COUNCIL_FORCE_PROVIDER`
- `OLLAMA_URL`
- `OLLAMA_MODEL`
- `COUNCIL_RATE_LIMIT_REQUESTS`
- `COUNCIL_RATE_LIMIT_WINDOW_SECONDS`

## Run CLI
```bash
python council.py
```

## Run Telegram Bot
```bash
export TELEGRAM_BOT_TOKEN=your_token
python telegram_bot.py
```

## Run with Local Models
```bash
export COUNCIL_FORCE_PROVIDER=ollama
export OLLAMA_URL=http://localhost:11434/api/generate
export OLLAMA_MODEL=llama3
python council.py
```

## Run Dashboard (local only)
```bash
pip install -r requirements-dashboard.txt
streamlit run dashboard.py
```

## Optional evidence folder
Place evidence files in `docs/` for retrieval at runtime, for example:

```text
docs/
  threat_model.md
  cloud_architecture.pdf
  wiz_scan_results.json
```

## Documentation
- [Engineering Handoff](ENGINEERING_HANDOFF.md)
