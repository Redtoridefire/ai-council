# AI Council System

Multi-agent AI decision engine using Claude, OpenAI, and Gemini.

## Features
- Parallel multi-agent reasoning
- Red team logic + cyber analysis
- Debate and critique phases
- Chairman synthesis decision
- Evidence injection (RAG) from `docs/`
- Weighted council voting (`confidence` + `risk_score` aggregation)
- SQLite-backed council memory for previous decisions

## Run
```bash
python council.py
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

## Documentation
- [Engineering Handoff](ENGINEERING_HANDOFF.md)
