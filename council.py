import json
from concurrent.futures import ThreadPoolExecutor

from claude_client import MODEL_CHAIR, ask_claude
from memory_store import CouncilMemory
from model_router import route_model
from rag import EvidenceRetriever, format_evidence_for_prompt
from voting import aggregate_weighted_scores, parse_structured_response

AGENTS = [
    "Chief Information Security Officer",
    "Security Engineer",
    "Technology Lawyer",
    "Chief Financial Officer",
    "Devil's Advocate Risk Analyst",
    "AI Reasoning Red Team",
    "Cybersecurity Red Team",
]

AGENT_MODELS = {
    "Chief Information Security Officer": "claude",
    "Security Engineer": "openai",
    "Technology Lawyer": "claude",
    "Chief Financial Officer": "openai",
    "Devil's Advocate Risk Analyst": "openai",
    "AI Reasoning Red Team": "claude",
    "Cybersecurity Red Team": "openai",
}


def run_agent(role, question, evidence_context, memory_context):
    if role == "AI Reasoning Red Team":
        prompt = f"""
You are an adversarial AI reasoning expert.

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

Focus on logical flaws, hidden assumptions, bias, and missing evidence.
"""

    elif role == "Cybersecurity Red Team":
        prompt = f"""
You are a cybersecurity offensive operator.

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

Identify attack paths, exploitation scenarios, privilege escalation,
and architecture weaknesses.
"""

    else:
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
"""

    provider = AGENT_MODELS[role]
    answer = route_model(provider, prompt)
    return role, answer


def critique_phase(role, original_answers, question, evidence_context):
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

    provider = AGENT_MODELS[role]
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


def main():
    question = input("Enter council question: ")

    retriever = EvidenceRetriever.from_docs_dir("docs")
    evidence_chunks = retriever.retrieve(question, top_k=4)
    evidence_context = format_evidence_for_prompt(evidence_chunks)

    memory = CouncilMemory("council_memory.db")
    memory_context = _format_recent_memory(memory)

    responses = {}
    parsed_responses = {}

    print("\nRunning council analysis...\n")

    with ThreadPoolExecutor() as executor:
        results = executor.map(
            lambda role: run_agent(role, question, evidence_context, memory_context), AGENTS
        )

    for role, answer in results:
        print(f"\n--- {role} ---\n")
        print(answer)
        responses[role] = answer
        parsed_responses[role] = parse_structured_response(answer)

    aggregate = aggregate_weighted_scores(parsed_responses)
    print("\n--- WEIGHTED COUNCIL METRICS ---\n")
    print(json.dumps(aggregate, indent=2))

    print("\nRunning critique phase...\n")

    critiques = {}
    compiled = ""
    for role, answer in responses.items():
        compiled += f"\n\n[{role}]\n{answer}"

    with ThreadPoolExecutor() as executor:
        critique_results = executor.map(
            lambda role: critique_phase(role, compiled, question, evidence_context), AGENTS
        )

    for role, critique in critique_results:
        print(f"\n--- {role} Critique ---\n")
        print(critique)
        critiques[role] = critique

    print("\n--- CHAIRMAN DECISION ---\n")
    decision = chairman_decision(
        question,
        responses,
        critiques,
        aggregate,
        evidence_context,
        memory_context,
    )
    print(decision)

    memory.save_decision(
        question=question,
        final_decision=decision,
        aggregate=aggregate,
        responses=responses,
    )


if __name__ == "__main__":
    main()
