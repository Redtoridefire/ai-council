import os

import requests
from claude_client import ask_claude
from google import genai
from openai import OpenAI

openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def ask_openai(prompt):
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
    )
    return response.choices[0].message.content


def ask_gemini(prompt):
    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text


def ask_ollama(prompt, model: str = OLLAMA_MODEL):
    response = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("response", "")


def route_model(provider, prompt):
    if provider == "claude":
        return ask_claude(prompt)
    if provider == "openai":
        return ask_openai(prompt)
    if provider == "gemini":
        return ask_gemini(prompt)
    if provider in {"ollama", "local"}:
        return ask_ollama(prompt)
    raise ValueError(f"Unknown provider: {provider}")
