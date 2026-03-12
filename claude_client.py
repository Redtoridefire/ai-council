
import os
import anthropic

MODEL_AGENT = "claude-haiku-4-5-20251001"
MODEL_CHAIR = "claude-sonnet-4-6"

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def ask_claude(prompt, model=MODEL_AGENT, max_tokens=500):
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
