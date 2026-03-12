# AI Council System — Engineering Handoff Document

**Author:** Mike Czarnecki
**Purpose:** Multi-Agent AI Strategic Advisory System

## 1. Project Overview

The AI Council System is a multi-agent reasoning framework designed to simulate a panel of expert advisors analyzing complex questions.

It was initially built as an experimental AI decision system for cybersecurity, fintech, and technology risk analysis.

The system orchestrates multiple AI agents with different professional roles, allows them to generate independent analysis, critique each other, and then produces a final Chairman decision.

The design goal is to replicate executive-level advisory reasoning rather than single-model responses.

## 2. Current System Architecture

The system operates in three phases:

### Phase 1 — Independent Analysis
All 11 agents analyze the problem in parallel, each returning structured JSON with `recommendation`, `confidence`, `risk_score`, `reasoning`, `risks`, and `benefits`.

### Phase 2 — Critique Phase
All 11 agents review the full set of Phase 1 responses and challenge weaknesses, overlooked risks, and contradictions — also run in parallel.

### Phase 3 — Chairman Decision
Claude Sonnet synthesizes all Phase 1 responses, Phase 2 critiques, weighted aggregate metrics, evidence context, and memory context into a final recommendation.

### Architecture Flow

```text
User Question
      ↓
RAG Evidence Retrieval (docs/ → TF-IDF → top-k chunks)
      ↓
SQLite Memory Context (last 3 council decisions)
      ↓
Phase 1: Parallel Agent Analysis (11 agents)
      ↓
Weighted Score Aggregation (confidence, risk, leading recommendation)
      ↓
Phase 2: Parallel Critique Phase (11 agents reviewing all Phase 1 output)
      ↓
Phase 3: Chairman Synthesis (Claude Sonnet)
      ↓
Save to SQLite Memory + Log Telemetry
```

## 3. Current Agents (11 total)

| Role | Default Provider | Weight |
|---|---|---|
| Chief Information Security Officer | Claude | 1.4 |
| Security Engineer | OpenAI | 1.3 |
| Technology Lawyer | Claude | 1.1 |
| Chief Financial Officer | OpenAI | 1.1 |
| Devil's Advocate Risk Analyst | OpenAI | 1.0 |
| AI Reasoning Red Team | Claude | 1.0 |
| Cybersecurity Red Team | OpenAI | 1.4 |
| Cloud Architect | OpenAI | 1.2 |
| Threat Intelligence Analyst | Claude | 1.3 |
| Compliance Officer | Claude | 1.2 |
| AI Safety Officer | Claude | 1.2 |

## 4. Model Routing

Different agents use different LLM providers. The router supports:

| Provider | Use | Env var |
|---|---|---|
| Claude (Haiku) | Agent reasoning | `ANTHROPIC_API_KEY` |
| Claude (Sonnet) | Chairman synthesis | `ANTHROPIC_API_KEY` |
| OpenAI (gpt-4o-mini) | Engineering / financial analysis | `OPENAI_API_KEY` |
| Gemini (gemini-2.0-flash) | Optional routing target | `GEMINI_API_KEY` |
| Ollama | Local model inference | `OLLAMA_URL`, `OLLAMA_MODEL` |

Set `COUNCIL_FORCE_PROVIDER=ollama` (or any provider) to route all agents to a single provider.

## 5. Code Structure

```text
ai-council/
├── council.py          # Main orchestration: Phase 1 → Phase 2 → Chairman
├── claude_client.py    # Anthropic SDK wrapper (Haiku for agents, Sonnet for chairman)
├── model_router.py     # Multi-provider routing with thread-safe rate limiting
├── voting.py           # Structured response parsing + weighted score aggregation
├── memory_store.py     # SQLite persistence of council decisions
├── rag.py              # TF-IDF evidence retrieval from docs/ directory
├── security.py         # API key redaction + SHA256 pseudonymization
├── telemetry.py        # SQLite telemetry event logging
├── telegram_bot.py     # Telegram bot interface (/council command)
├── dashboard.py        # Streamlit visualization dashboard
└── requirements.txt
```

## 6. Implemented Features

- Multi-agent parallel reasoning (Phase 1 + Phase 2 via `ThreadPoolExecutor`)
- Structured JSON output from agents (`recommendation`, `confidence`, `risk_score`, etc.)
- Weighted council voting with per-role weights
- RAG evidence injection from `docs/` (`.md`, `.txt`, `.json`, `.pdf` via TF-IDF + cosine similarity)
- SQLite-backed council memory (last 3 decisions injected into prompts)
- Chairman synthesis via Claude Sonnet
- Telegram bot interface (`/council <question>`)
- Local model support via Ollama-compatible endpoint
- Streamlit dashboard (confidence, risk, disagreement trends, telemetry)
- Provider-level rate limiting (thread-safe, default: 30 req/60s)
- Secret redaction in telemetry logs
- Telemetry event logging (duration, evidence chunk count, confidence, risk)

## 7. Rate Limiting

Rate limiting is applied per-provider using a sliding window. The default is **30 requests per 60 seconds** per provider, which comfortably covers a full council run:

- Phase 1: 6 Claude + 5 OpenAI requests
- Phase 2: 6 Claude + 5 OpenAI requests
- Chairman: 1 Claude request
- **Total: 13 Claude + 10 OpenAI per run**

Override via environment:
```bash
export COUNCIL_RATE_LIMIT_REQUESTS=30
export COUNCIL_RATE_LIMIT_WINDOW_SECONDS=60
```

## 8. Security Considerations

- API keys are never logged; telemetry metadata is redacted via `security.py`
- `pseudonymize_text` SHA256-hashes question content before storing in telemetry
- `redact_sensitive_text` strips common API key patterns (`sk-*`, `AIza*`, `xoxb-*`) from logs
- For enterprise use, private LLM deployment (local Ollama) is recommended

## 9. Known Limitations

- **RAG uses TF-IDF**, not dense vector embeddings. Semantic similarity is limited. For production, consider ChromaDB or FAISS with embedding models.
- **No retry logic** on individual LLM calls. A transient API error in an agent fails that agent's response silently (falls back to "Unparsed" in voting).
- **Memory context is limited to 3 recent decisions** by default. The `get_recent(limit=3)` call in `council.py` can be adjusted.
- **Telegram response truncated at 4096 characters** (Telegram API limit). Long chairman decisions get cut off.

## 10. Long-Term Vision

The AI Council could evolve into an **AI Executive Decision Engine**.

Use cases:
- Cybersecurity strategy
- Technology architecture
- Investment analysis
- Regulatory risk
- M&A technology evaluation

The goal is structured multi-perspective reasoning, not single-model answers.

## 11. Priority Future Upgrades

- **Dense vector RAG**: Replace TF-IDF with embedding-based retrieval (ChromaDB, FAISS)
- **Agent retry logic**: Retry failed LLM calls with exponential backoff
- **Debate loops**: Allow agents to argue multiple rounds before chairman synthesis
- **Risk heatmap**: Generate impact vs likelihood matrix from agent outputs
- **Azure OpenAI support**: Add routing target for enterprise deployments
