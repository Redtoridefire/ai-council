"""
FastAPI REST interface for the AI Council.

Run with:
    uvicorn api:app --host 0.0.0.0 --port 8000

Endpoints:
    POST /council   — Run a full council session
    GET  /health    — Liveness check
    GET  /decisions — Recent stored decisions
"""

import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from council import run_council
from memory_store import CouncilMemory

app = FastAPI(title="AI Council API", version="1.0")


class CouncilRequest(BaseModel):
    question: str = Field(..., description="The question for the council to evaluate.")
    docs_dir: str = Field("docs", description="Directory of evidence documents for RAG.")
    debate_rounds: int = Field(0, ge=0, le=3, description="Number of debate rounds (0–3).")


class CouncilResponse(BaseModel):
    question: str
    aggregate: dict
    decision: str
    debate_rounds_run: int
    agent_models: dict


class DecisionSummary(BaseModel):
    question: str
    council_confidence: float
    council_risk_score: float
    leading_recommendation: str
    created_at: str


@app.post("/council", response_model=CouncilResponse)
async def council_endpoint(request: CouncilRequest):
    """Run a full council analysis and return the chairman's decision with aggregate metrics."""
    try:
        result = await asyncio.to_thread(
            run_council,
            request.question,
            request.docs_dir,
            "council_memory.db",
            request.debate_rounds,
            False,  # no streaming in API mode
        )
        return CouncilResponse(
            question=result["question"],
            aggregate=result["aggregate"],
            decision=result["decision"],
            debate_rounds_run=request.debate_rounds,
            agent_models=result["agent_models"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/decisions", response_model=list[DecisionSummary])
async def recent_decisions(limit: int = 10):
    """Return the most recent council decisions from memory."""
    try:
        memory = CouncilMemory("council_memory.db")
        records = memory.get_recent(limit=limit)
        return [
            DecisionSummary(
                question=r["question"],
                council_confidence=r["aggregate"].get("council_confidence", 0),
                council_risk_score=r["aggregate"].get("council_risk_score", 0),
                leading_recommendation=r["aggregate"].get("leading_recommendation", "unknown"),
                created_at=r["created_at"],
            )
            for r in records
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}
