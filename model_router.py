
import os
from claude_client import ask_claude
from openai import OpenAI
from google import genai

openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def ask_openai(prompt):
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=400
    )
    return response.choices[0].message.content

def ask_gemini(prompt):
    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return response.text

def route_model(provider, prompt):
    if provider == "claude":
        return ask_claude(prompt)
    if provider == "openai":
        return ask_openai(prompt)
    if provider == "gemini":
        return ask_gemini(prompt)
    raise ValueError("Unknown provider")
