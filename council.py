
from model_router import route_model
from claude_client import ask_claude, MODEL_CHAIR
from concurrent.futures import ThreadPoolExecutor

AGENTS = [
    "Chief Information Security Officer",
    "Security Engineer",
    "Technology Lawyer",
    "Chief Financial Officer",
    "Devil's Advocate Risk Analyst",
    "AI Reasoning Red Team",
    "Cybersecurity Red Team"
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

def run_agent(role, question):

    if role == "AI Reasoning Red Team":
        prompt = f"""
You are an adversarial AI reasoning expert.

Question:
{question}

Identify logical flaws, hidden assumptions, bias, and missing evidence.
"""

    elif role == "Cybersecurity Red Team":
        prompt = f"""
You are a cybersecurity offensive operator.

Question:
{question}

Identify attack paths, exploitation scenarios, privilege escalation,
and architecture weaknesses.
"""

    else:
        prompt = f"""
You are the {role} in a fintech technology advisory council.

Question:
{question}

Provide:
Recommendation
Reasoning
Risks
Benefits
Confidence (0-100)
"""

    provider = AGENT_MODELS[role]
    answer = route_model(provider, prompt)

    return role, answer


def critique_phase(role, original_answers, question):

    prompt = f"""
You are the {role} reviewing the council's answers.

Question:
{question}

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


def chairman_decision(question, responses, critiques):

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

INITIAL ANALYSIS
{compiled_responses}

CRITIQUE PHASE
{compiled_critiques}

Provide final recommendation, risk analysis and confidence.
"""

    decision = ask_claude(prompt, model=MODEL_CHAIR, max_tokens=800)
    return decision


def main():

    question = input("Enter council question: ")
    responses = {}

    print("\nRunning council analysis...\n")

    with ThreadPoolExecutor() as executor:
        results = executor.map(lambda role: run_agent(role, question), AGENTS)

    for role, answer in results:
        print(f"\n--- {role} ---\n")
        print(answer)
        responses[role] = answer

    print("\nRunning critique phase...\n")

    critiques = {}
    compiled = ""

    for role, answer in responses.items():
        compiled += f"\n\n[{role}]\n{answer}"

    with ThreadPoolExecutor() as executor:
        critique_results = executor.map(
            lambda role: critique_phase(role, compiled, question), AGENTS
        )

    for role, critique in critique_results:
        print(f"\n--- {role} Critique ---\n")
        print(critique)
        critiques[role] = critique

    print("\n--- CHAIRMAN DECISION ---\n")

    decision = chairman_decision(question, responses, critiques)
    print(decision)


if __name__ == "__main__":
    main()
