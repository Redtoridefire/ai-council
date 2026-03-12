# AI Council System

Multi-agent AI decision engine using Claude, OpenAI, Gemini, and local model routing.

## Features
- Parallel multi-agent reasoning (11 specialist agents)
- Red team logic + cyber analysis
- Debate and critique phases (configurable debate rounds)
- Chairman synthesis decision with live token streaming
- Per-agent memory context (each agent sees its own past responses)
- Evidence injection (RAG) from `docs/` — dense embeddings via `sentence-transformers` with TF-IDF fallback
- Weighted council voting (`confidence` + `risk_score` aggregation)
- SQLite-backed council memory for previous decisions
- Per-agent error isolation (one failed agent never crashes the run)
- Telegram bot interface (`/council <question>`)
- Local model support via Ollama-compatible HTTP endpoint
- Streamlit dashboard: confidence/risk trends, disagreement, agent risk heatmap
- FastAPI REST endpoint for programmatic access
- Thread-safe provider rate limiting with exponential backoff retry
- Prompt/log redaction helpers for basic secret hygiene

## Run CLI
```bash
python council.py
```
Prompts for question and optional debate rounds. Chairman decision streams live.

## Run API Server
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```
- `POST /council` — run a council session
- `GET  /decisions` — list recent decisions
- `GET  /health` — liveness check

Interactive docs at `http://localhost:8000/docs`

## Run Telegram Bot
```bash
export TELEGRAM_BOT_TOKEN=your_token
python telegram_bot.py
```

## Run with Local Models
Route all agents through a local Ollama endpoint:
```bash
export COUNCIL_FORCE_PROVIDER=ollama
export OLLAMA_URL=http://localhost:11434/api/generate
export OLLAMA_MODEL=llama3
python council.py
```

## Run Dashboard
```bash
streamlit run dashboard.py
```

## Debate Rounds
Run multi-round adversarial debate before chairman synthesis:
```bash
# In CLI, enter 1-3 at the "Debate rounds" prompt
# Via API: POST /council with {"question": "...", "debate_rounds": 2}
```

## Dense RAG Embeddings
By default, evidence documents in `docs/` are indexed with `sentence-transformers` (`all-MiniLM-L6-v2`).
The model is downloaded automatically on first run (~80 MB).

To use TF-IDF instead:
```bash
export COUNCIL_DENSE_EMBEDDINGS=0
```

To use a different embedding model:
```bash
export COUNCIL_EMBEDDING_MODEL=all-mpnet-base-v2
```

## Optional Evidence Folder
Place evidence files in `docs/` for retrieval at runtime:
```text
docs/
  threat_model.md
  cloud_architecture.pdf
  wiz_scan_results.json
```

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for Claude agents and chairman |
| `OPENAI_API_KEY` | — | Required for OpenAI agents |
| `GEMINI_API_KEY` | — | Required if using Gemini routing |
| `TELEGRAM_BOT_TOKEN` | — | Required for Telegram bot |
| `COUNCIL_FORCE_PROVIDER` | — | Force all agents to one provider (e.g. `ollama`) |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | Local Ollama endpoint |
| `OLLAMA_MODEL` | `llama3` | Local model name |
| `COUNCIL_RATE_LIMIT_REQUESTS` | `30` | Max requests per provider per window |
| `COUNCIL_RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window in seconds |
| `COUNCIL_DENSE_EMBEDDINGS` | `1` | Set to `0` to use TF-IDF instead of dense RAG |
| `COUNCIL_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model for RAG |

## Documentation
- [Engineering Handoff](ENGINEERING_HANDOFF.md)
