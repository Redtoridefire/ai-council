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

## Run CLI
```bash
python council.py
```

## Run Telegram Bot (Phase 2 - Upgrade 4)
```bash
export TELEGRAM_BOT_TOKEN=your_token
python telegram_bot.py
```

## Run with Local Models (Phase 2 - Upgrade 5)
Use a local provider for all agents:

```bash
export COUNCIL_FORCE_PROVIDER=ollama
export OLLAMA_URL=http://localhost:11434/api/generate
export OLLAMA_MODEL=llama3
python council.py
```

## Run Dashboard (Phase 2 - Upgrade 6)
```bash
streamlit run dashboard.py
```

## Security + Rate Limit Controls (Phase 3)
```bash
export COUNCIL_RATE_LIMIT_REQUESTS=8
export COUNCIL_RATE_LIMIT_WINDOW_SECONDS=60
```

## Optional evidence folder
Place evidence files in `docs/` for retrieval at runtime, for example:

```text
docs/
  threat_model.md
  cloud_architecture.pdf
  wiz_scan_results.json
```

## Environment Variables
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN` (for Telegram interface)
- `COUNCIL_FORCE_PROVIDER` (optional, e.g., `ollama`)
- `OLLAMA_URL` (optional local endpoint)
- `OLLAMA_MODEL` (optional local model name)
- `COUNCIL_RATE_LIMIT_REQUESTS` (optional)
- `COUNCIL_RATE_LIMIT_WINDOW_SECONDS` (optional)

## Documentation
- [Engineering Handoff](ENGINEERING_HANDOFF.md)
