# AI Council System — Engineering Handoff Document

**Author:** Mike Czarnecki  
**Purpose:** Multi-Agent AI Strategic Advisory System

## 1. Project Overview

The AI Council System is a multi-agent reasoning framework designed to simulate a panel of expert advisors analyzing complex questions.

It was initially built as an experimental AI decision system for cybersecurity, fintech, and technology risk analysis.

The system orchestrates multiple AI agents with different professional roles, allows them to generate independent analysis, critique each other, and then produces a final Chairman decision.

The design goal is to replicate executive-level advisory reasoning rather than single-model responses.

## 2. Current System Architecture

The system currently operates in three phases:

### Phase 1 — Independent Analysis
Each agent analyzes the problem independently.

### Phase 2 — Critique Phase
Agents review the entire council's responses and challenge weaknesses.

### Phase 3 — Chairman Decision
A final synthesis agent consolidates all findings.

### Architecture Flow

```text
User Question
      ↓
Parallel Agent Analysis
(CISO, Engineer, Lawyer, CFO)
      ↓
Devil's Advocate Risk Analysis
      ↓
AI Reasoning Red Team
      ↓
Cybersecurity Red Team
      ↓
Peer Critique Phase
      ↓
Chairman Synthesis Decision
```

## 3. Current Agents

The system currently includes 7 agents:

1. **Chief Information Security Officer** — Strategic cyber risk analysis.
2. **Security Engineer** — Technical feasibility and architecture analysis.
3. **Technology Lawyer** — Regulatory and legal risk analysis.
4. **Chief Financial Officer** — Cost, ROI, and operational risk.
5. **Devil's Advocate Risk Analyst** — Challenges optimistic assumptions.
6. **AI Reasoning Red Team** — Identifies logical flaws and reasoning gaps.
7. **Cybersecurity Red Team** — Identifies attack paths and exploitation scenarios.

## 4. Model Routing

Different agents can use different LLM providers.

Current router supports:

| Provider | Use |
|---|---|
| Claude | Reasoning / Chairman |
| OpenAI | Engineering / financial analysis |
| Gemini | Optional model fallback |

## 5. Current Code Structure

```text
ai-council/
│
├── council.py
├── model_router.py
├── claude_client.py
├── requirements.txt
└── README.md
```

### `council.py`
Main orchestration script.

Responsibilities:
- run agent analysis
- run critique phase
- collect responses
- generate chairman decision

Uses parallel execution via `ThreadPoolExecutor`.

### `model_router.py`
Handles routing prompts to different LLM providers.

Currently supports:
- Claude
- OpenAI
- Gemini

Future versions should support:
- Ollama
- Local LLMs
- Azure OpenAI

### `claude_client.py`
Handles calls to Anthropic models.

Current configuration:
- Agent model: `claude-haiku-4-5-20251001`
- Chairman model: `claude-sonnet-4-6`

## 6. Current Features Implemented

- ✔ Multi-agent reasoning
- ✔ Parallel agent execution
- ✔ Debate-style reasoning
- ✔ Critique phase
- ✔ Adversarial reasoning agent
- ✔ Cybersecurity red team agent
- ✔ Multi-model routing
- ✔ Chairman synthesis

## 7. Known Limitations

The current system has several limitations:
- No Knowledge Base: Agents only rely on the prompt; no document ingestion yet.
- No Memory: The council does not remember previous decisions.
- No Confidence Aggregation: Confidence scores are not aggregated across agents.
- No Weighted Voting: Agents currently contribute equally.
- No Structured Output: Responses are free-form text.
- No Telemetry: No logging or analytics.

## 8. Priority Future Upgrades

### Upgrade 1 — Evidence Injection (RAG)
Most important next feature.

Agents should be able to analyze real documents.

Example folder:

```text
docs/
   threat_model.md
   cloud_architecture.pdf
   wiz_scan_results.json
```

System workflow:

```text
documents
   ↓
vector embeddings
   ↓
semantic retrieval
   ↓
inject evidence into prompts
```

Recommended stack:
- LangChain
- LlamaIndex
- ChromaDB
- FAISS

Goal: agents reason using actual evidence rather than only prompts.

### Upgrade 2 — Weighted Agent Voting
Agents should output structured responses:
- Recommendation
- Confidence
- RiskScore

Then aggregate:

```text
CouncilConfidence = weighted_average(agent_confidence)
```

Future extension: agent weighting based on domain expertise.

### Upgrade 3 — Agent Memory
Persist past council decisions.

Potential implementation:
- SQLite
- Redis
- Postgres

Example use: “What did the council previously decide about Wiz?”

### Upgrade 4 — Telegram Interface
Allow mobile interaction.

Example flow:

```text
/council should we adopt Wiz?
Telegram bot → council.py → response
```

### Upgrade 5 — Local Model Support
Allow running agents on local models.

Recommended stack:
- Ollama
- Llama 3
- Mixtral
- DeepSeek

Benefits:
- privacy
- no API costs
- faster local inference

### Upgrade 6 — Visualization Dashboard
Build a UI showing:
- agent disagreements
- risk scoring
- consensus strength

Possible stack:
- Streamlit
- NextJS
- FastAPI

### Upgrade 7 — Council Expansion
Future council members:
- Cloud Architect — infrastructure decisions.
- Threat Intelligence Analyst — adversary modeling.
- Compliance Officer — regulatory mapping.
- AI Safety Officer — AI governance review.

## 9. Security Considerations

This system may analyze sensitive data.

Recommended controls:
- API key isolation
- prompt redaction
- model response logging
- rate limiting

If used in enterprise environments, private LLM deployment is recommended.

## 10. Long-Term Vision

The AI Council could evolve into an **AI Executive Decision Engine**.

Use cases:
- Cybersecurity strategy
- Technology architecture
- Investment analysis
- Regulatory risk
- M&A technology evaluation

The goal is structured multi-perspective reasoning, not single-model answers.

## 11. Immediate Next Development Task

Next development milestone: **RAG Evidence Injection**.

Steps:
1. Create `/docs` ingestion pipeline.
2. Generate embeddings.
3. Implement semantic retrieval.
4. Inject retrieved context into agent prompts.

## 12. Optional Experimental Ideas

Future advanced features:
- Agent Disagreement Scoring — measure divergence between agents.
- Debate Loops — allow agents to argue multiple rounds.
- Self-Critique LLM — one agent evaluates reasoning quality.
- Risk Heatmap — generate a matrix of impact vs likelihood.
