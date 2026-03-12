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


def run_agent(role, question, evidence_context, memory_context, agent_models, role_memory_context=""):
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

    role_memory_section = (
        f"\nYour previous responses on similar questions:\n{role_memory_context}\n"
        if role_memory_context
        else ""
    )

    prompt = f"""
You are the {role} in a fintech technology advisory council.

Question:
{question}

Relevant evidence:
{evidence_context}

Recent council decisions:
{memory_context}
{role_memory_section}
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


def _run_agent_safe(role, question, evidence_context, memory_context, agent_models, role_memory_context=""):
    """Wraps run_agent so a single agent failure never crashes the full council run."""
    try:
        return run_agent(role, question, evidence_context, memory_context, agent_models, role_memory_context)
    except Exception as exc:
        fallback = json.dumps({
            "recommendation": "Error",
            "confidence": 0,
            "risk_score": 100,
            "reasoning": f"Agent failed: {exc}",
            "risks": "Agent unavailable",
            "benefits": "",
        })
        return role, fallback


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


def _critique_phase_safe(role, original_answers, question, evidence_context, agent_models):
    """Wraps critique_phase so a single agent failure never crashes the critique round."""
    try:
        return critique_phase(role, original_answers, question, evidence_context, agent_models)
    except Exception as exc:
        return role, f"Critique unavailable: {exc}"


def _rebuttal_phase(role, critiques_text, question, evidence_context, agent_models):
    """Agents respond to the critique round, updating their positions."""
    prompt = f"""
You are the {role} in a fintech technology advisory council.

The council has completed an initial analysis and critique round on this question:
{question}

Relevant evidence:
{evidence_context}

Council critiques from the previous round:
{critiques_text}

In light of these critiques, provide your updated analysis.
Return STRICT JSON with fields:
- recommendation
- confidence (0-100)
- risk_score (0-100)
- reasoning
- risks
- benefits
"""
    try:
        provider = agent_models[role]
        answer = route_model(provider, prompt)
        return role, answer
    except Exception as exc:
        fallback = json.dumps({
            "recommendation": "Error",
            "confidence": 0,
            "risk_score": 100,
            "reasoning": f"Rebuttal failed: {exc}",
            "risks": "Agent unavailable",
            "benefits": "",
        })
        return role, fallback


def chairman_decision(
    question,
    responses,
    critiques,
    aggregate,
    evidence_context,
    memory_context,
    debate_history=None,
    stream_callback=None,
):
    compiled_responses = "".join(f"\n\n[{role}]\n{answer}" for role, answer in responses.items())
    compiled_critiques = "".join(f"\n\n[{role}]\n{critique}" for role, critique in critiques.items())

    debate_section = ""
    if debate_history:
        for round_label, (round_responses, round_critiques) in debate_history.items():
            debate_section += f"\n\n=== {round_label} ===\n"
            debate_section += "".join(f"\n[{role}]\n{answer}" for role, answer in round_responses.items())
            debate_section += f"\n\n--- {round_label} Critiques ---\n"
            debate_section += "".join(f"\n[{role}]\n{c}" for role, c in round_critiques.items())

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
{debate_section}
Provide a final recommendation, risk analysis, and confidence.
"""

    return ask_claude(prompt, model=MODEL_CHAIR, max_tokens=1200, stream_callback=stream_callback)


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


def _format_role_memory(memory: CouncilMemory, role: str) -> str:
    recent = memory.get_recent_for_role(role, limit=2)
    if not recent:
        return ""

    lines = []
    for item in recent:
        snippet = item["role_response"][:300].strip()
        if snippet:
            lines.append(
                f"- [{item['created_at']}] Q: {item['question']}\n  Your response: {snippet}..."
            )
    return "\n".join(lines)


def run_council(
    question: str,
    docs_dir: str = "docs",
    db_path: str = "council_memory.db",
    debate_rounds: int = 0,
    stream_chairman: bool = False,
):
    start = time.time()
    agent_models = _resolve_agent_models()
    telemetry = TelemetryStore(db_path)

    retriever = EvidenceRetriever.from_docs_dir(docs_dir)
    evidence_chunks = retriever.retrieve(question, top_k=4)
    evidence_context = format_evidence_for_prompt(evidence_chunks)

    memory = CouncilMemory(db_path)
    memory_context = _format_recent_memory(memory)

    # Phase 1: parallel agent analysis with per-role memory context
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                _run_agent_safe,
                role, question, evidence_context, memory_context,
                agent_models, _format_role_memory(memory, role),
            )
            for role in AGENTS
        ]
        phase1_results = [f.result() for f in futures]

    responses = {}
    parsed_responses = {}
    for role, answer in phase1_results:
        responses[role] = answer
        parsed_responses[role] = parse_structured_response(answer)

    aggregate = aggregate_weighted_scores(parsed_responses)

    # Phase 2: parallel critique
    compiled = "".join(f"\n\n[{role}]\n{answer}" for role, answer in responses.items())

    with ThreadPoolExecutor() as executor:
        critique_futures = [
            executor.submit(_critique_phase_safe, role, compiled, question, evidence_context, agent_models)
            for role in AGENTS
        ]
        critique_results = [f.result() for f in critique_futures]

    critiques = {role: critique for role, critique in critique_results}

    # Optional debate rounds: agents rebut critiques, new critiques generated
    debate_history = {}
    current_critiques = critiques

    for round_num in range(1, debate_rounds + 1):
        round_label = f"Debate Round {round_num}"
        critiques_text = "".join(
            f"\n[{role} critique]\n{c}" for role, c in current_critiques.items()
        )

        with ThreadPoolExecutor() as executor:
            rebuttal_futures = [
                executor.submit(_rebuttal_phase, role, critiques_text, question, evidence_context, agent_models)
                for role in AGENTS
            ]
            rebuttal_responses = {role: answer for role, answer in [f.result() for f in rebuttal_futures]}

        compiled_rebuttal = "".join(f"\n\n[{role}]\n{answer}" for role, answer in rebuttal_responses.items())

        with ThreadPoolExecutor() as executor:
            new_critique_futures = [
                executor.submit(_critique_phase_safe, role, compiled_rebuttal, question, evidence_context, agent_models)
                for role in AGENTS
            ]
            new_critiques = {role: critique for role, critique in [f.result() for f in new_critique_futures]}

        debate_history[round_label] = (rebuttal_responses, new_critiques)
        current_critiques = new_critiques

    # Phase 3: Chairman synthesis (optionally streamed token-by-token)
    if stream_chairman:
        print("\n--- CHAIRMAN DECISION ---\n")
    stream_cb = (lambda t: print(t, end="", flush=True)) if stream_chairman else None

    decision = chairman_decision(
        question,
        responses,
        critiques,
        aggregate,
        evidence_context,
        memory_context,
        debate_history=debate_history if debate_history else None,
        stream_callback=stream_cb,
    )
    if stream_chairman:
        print()  # newline after streamed output

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
            "debate_rounds": debate_rounds,
        },
    )

    return {
        "question": question,
        "responses": responses,
        "parsed_responses": {k: vars(v) for k, v in parsed_responses.items()},
        "aggregate": aggregate,
        "critiques": critiques,
        "debate_history": debate_history,
        "decision": decision,
        "evidence_context": evidence_context,
        "memory_context": memory_context,
        "agent_models": agent_models,
    }


def main():
    question = input("Enter council question: ")
    debate_rounds_input = input("Debate rounds (0 for none, default 0): ").strip()
    debate_rounds = int(debate_rounds_input) if debate_rounds_input.isdigit() else 0

    print("\nRunning council analysis...\n")
    result = run_council(question, debate_rounds=debate_rounds, stream_chairman=True)

    for role, answer in result["responses"].items():
        print(f"\n--- {role} ---\n")
        print(answer)

    print("\n--- WEIGHTED COUNCIL METRICS ---\n")
    print(json.dumps(result["aggregate"], indent=2))

    print("\n--- CRITIQUE PHASE ---\n")
    for role, critique in result["critiques"].items():
        print(f"\n--- {role} Critique ---\n")
        print(critique)

    for round_label, (rebuttals, new_critiques) in result["debate_history"].items():
        print(f"\n=== {round_label} ===\n")
        for role, answer in rebuttals.items():
            print(f"\n--- {role} Rebuttal ---\n")
            print(answer)
        print(f"\n--- {round_label} Critiques ---\n")
        for role, critique in new_critiques.items():
            print(f"\n--- {role} ---\n")
            print(critique)

    # Chairman decision was already streamed live; stored copy follows
    print("\n(Chairman decision streamed above.)")


if __name__ == "__main__":
    main()
