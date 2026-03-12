import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from claude_client import MODEL_CHAIR, ask_claude
from memory_store import CouncilMemory
from model_router import route_model
from rag import EvidenceRetriever, format_evidence_for_prompt
from security import pseudonymize_text, redact_sensitive_text
from telemetry import TelemetryStore
from voting import aggregate_weighted_scores, parse_structured_response

AGENTS = [
    "Chief Information Security Officer",
    "Security Engineer",
    "Technology Lawyer",
    "Chief Financial Officer",
    "Devil's Advocate Risk Analyst",
    "AI Reasoning Red Team",
    "Cybersecurity Red Team",
    "Cloud Architect",
    "Threat Intelligence Analyst",
    "Compliance Officer",
    "AI Safety Officer",
]

DEFAULT_AGENT_MODELS = {
    "Chief Information Security Officer": "claude",
    "Security Engineer": "openai",
    "Technology Lawyer": "claude",
    "Chief Financial Officer": "openai",
    "Devil's Advocate Risk Analyst": "openai",
    "AI Reasoning Red Team": "claude",
    "Cybersecurity Red Team": "openai",
    "Cloud Architect": "openai",
    "Threat Intelligence Analyst": "claude",
    "Compliance Officer": "claude",
    "AI Safety Officer": "claude",
}


def _resolve_agent_models():
    force_provider = os.environ.get("COUNCIL_FORCE_PROVIDER")
    if not force_provider:
        return DEFAULT_AGENT_MODELS
    return {role: force_provider for role in AGENTS}


def run_agent(role, question, evidence_context, memory_context, agent_models):
    if role == "AI Reasoning Red Team":
        role_instructions = "Focus on logical flaws, hidden assumptions, bias, and missing evidence."
    elif role == "Cybersecurity Red Team":
        role_instructions = (
            "Identify attack paths, exploitation scenarios, privilege escalation, "
            "and architecture weaknesses."
        )
    elif role == "Cloud Architect":
        role_instructions = "Focus on infrastructure resilience, scalability, and cloud design tradeoffs."
    elif role == "Threat Intelligence Analyst":
        role_instructions = "Focus on adversary behavior, threat trends, and threat likelihoods."
    elif role == "Compliance Officer":
        role_instructions = "Focus on compliance mappings, audit obligations, and control gaps."
    elif role == "AI Safety Officer":
        role_instructions = "Focus on AI governance, misuse risk, and model safety controls."
    else:
        role_instructions = "Focus on your domain expertise and provide a balanced advisory perspective."

    prompt = f"""
You are the {role} in a fintech technology advisory council.

Question:
{question}

Relevant evidence:
{evidence_context}

Recent council memory:
{memory_context}

Return STRICT JSON with fields:
- recommendation
- confidence (0-100)
- risk_score (0-100)
- reasoning
- risks
- benefits

{role_instructions}
"""

    provider = agent_models[role]
    answer = route_model(provider, prompt)
    return role, answer


def critique_phase(role, original_answers, question, evidence_context, agent_models):
    prompt = f"""
You are the {role} reviewing the council's answers.

Question:
{question}

Relevant evidence:
{evidence_context}

Council responses:
{original_answers}

Your task:
1. Challenge weak reasoning
2. Identify overlooked risks
3. Highlight contradictions
"""

    provider = agent_models[role]
    critique = route_model(provider, prompt)
    return role, critique


def chairman_decision(question, responses, critiques, aggregate, evidence_context, memory_context):
    compiled_responses = ""
    compiled_critiques = ""

    for role, answer in responses.items():
        compiled_responses += f"\n\n[{role}]\n{answer}"

    for role, critique in critiques.items():
        compiled_critiques += f"\n\n[{role}]\n{critique}"

    prompt = f"""
You are the Chairman of a fintech advisory council.

The council evaluated this question:
{question}

Evidence context:
{evidence_context}

Recent council memory:
{memory_context}

Weighted council metrics:
- CouncilConfidence: {aggregate['council_confidence']}
- CouncilRiskScore: {aggregate['council_risk_score']}
- LeadingRecommendation: {aggregate['leading_recommendation']}

INITIAL ANALYSIS
{compiled_responses}

CRITIQUE PHASE
{compiled_critiques}

Provide a final recommendation, risk analysis, and confidence.
"""

    return ask_claude(prompt, model=MODEL_CHAIR, max_tokens=900)


def _format_recent_memory(memory: CouncilMemory) -> str:
    recent = memory.get_recent(limit=3)
    if not recent:
        return "No prior council decisions stored yet."

    lines = []
    for item in recent:
        lines.append(
            f"- [{item['created_at']}] Q: {item['question']} | "
            f"Confidence: {item['aggregate'].get('council_confidence')} | "
            f"Risk: {item['aggregate'].get('council_risk_score')}"
        )
    return "\n".join(lines)


def run_council(question: str, docs_dir: str = "docs", db_path: str = "council_memory.db"):
    start = time.time()
    agent_models = _resolve_agent_models()
    telemetry = TelemetryStore(db_path)

    retriever = EvidenceRetriever.from_docs_dir(docs_dir)
    evidence_chunks = retriever.retrieve(question, top_k=4)
    evidence_context = format_evidence_for_prompt(evidence_chunks)

    memory = CouncilMemory(db_path)
    memory_context = _format_recent_memory(memory)

    responses = {}
    parsed_responses = {}

    with ThreadPoolExecutor() as executor:
        results = executor.map(
            lambda role: run_agent(role, question, evidence_context, memory_context, agent_models),
            AGENTS,
        )

    for role, answer in results:
        responses[role] = answer
        parsed_responses[role] = parse_structured_response(answer)

    aggregate = aggregate_weighted_scores(parsed_responses)

    critiques = {}
    compiled = ""
    for role, answer in responses.items():
        compiled += f"\n\n[{role}]\n{answer}"

    with ThreadPoolExecutor() as executor:
        critique_results = executor.map(
            lambda role: critique_phase(role, compiled, question, evidence_context, agent_models),
            AGENTS,
        )

    for role, critique in critique_results:
        critiques[role] = critique

    decision = chairman_decision(
        question,
        responses,
        critiques,
        aggregate,
        evidence_context,
        memory_context,
    )

    memory.save_decision(
        question=question,
        final_decision=decision,
        aggregate=aggregate,
        responses=responses,
    )

    telemetry.log_event(
        "council_run_completed",
        {
            "question_hash": pseudonymize_text(question),
            "question_preview": redact_sensitive_text(question[:120]),
            "agent_count": len(AGENTS),
            "evidence_chunk_count": len(evidence_chunks),
            "duration_seconds": round(time.time() - start, 2),
            "council_confidence": aggregate.get("council_confidence"),
            "council_risk_score": aggregate.get("council_risk_score"),
            "leading_recommendation": aggregate.get("leading_recommendation"),
        },
    )

    return {
        "question": question,
        "responses": responses,
        "parsed_responses": {k: vars(v) for k, v in parsed_responses.items()},
        "aggregate": aggregate,
        "critiques": critiques,
        "decision": decision,
        "evidence_context": evidence_context,
        "memory_context": memory_context,
        "agent_models": agent_models,
    }


def main():
    question = input("Enter council question: ")
    result = run_council(question)

    print("\nRunning council analysis...\n")
    for role, answer in result["responses"].items():
        print(f"\n--- {role} ---\n")
        print(answer)

    print("\n--- WEIGHTED COUNCIL METRICS ---\n")
    print(json.dumps(result["aggregate"], indent=2))

    print("\nRunning critique phase...\n")
    for role, critique in result["critiques"].items():
        print(f"\n--- {role} Critique ---\n")
        print(critique)

    print("\n--- CHAIRMAN DECISION ---\n")
    print(result["decision"])


if __name__ == "__main__":
    main()
