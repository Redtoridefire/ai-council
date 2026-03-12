import os
import threading
import time
from collections import defaultdict, deque

import requests
from claude_client import ask_claude
from google import genai
from openai import OpenAI

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

# Default is 30 to comfortably support a full council run (11 agents × 2 phases + 1 chairman = 23
# requests per provider in the worst case, all within ~60 seconds).
RATE_LIMIT_REQUESTS = int(os.environ.get("COUNCIL_RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("COUNCIL_RATE_LIMIT_WINDOW_SECONDS", "60"))
_REQUEST_HISTORY: dict[str, deque] = defaultdict(deque)
_RATE_LIMIT_LOCK = threading.Lock()

_openai_client = None
_gemini_client = None
_CLIENT_LOCK = threading.Lock()


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        with _CLIENT_LOCK:
            if _openai_client is None:
                _openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _openai_client


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        with _CLIENT_LOCK:
            if _gemini_client is None:
                _gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _gemini_client


def _enforce_rate_limit(provider: str):
    with _RATE_LIMIT_LOCK:
        now = time.time()
        queue = _REQUEST_HISTORY[provider]

        while queue and now - queue[0] > RATE_LIMIT_WINDOW_SECONDS:
            queue.popleft()

        if len(queue) >= RATE_LIMIT_REQUESTS:
            wait_for = RATE_LIMIT_WINDOW_SECONDS - (now - queue[0])
            raise RuntimeError(
                f"Rate limit exceeded for {provider}. Try again in {max(1, int(wait_for))}s."
            )

        queue.append(now)


def _with_retry(fn, max_retries: int = 3):
    """Call fn(), retrying up to max_retries times with exponential backoff."""
    delay = 2
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception:
            if attempt == max_retries:
                raise
            time.sleep(delay)
            delay *= 2


def ask_openai(prompt: str) -> str:
    def _call():
        response = _get_openai_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
        return response.choices[0].message.content

    return _with_retry(_call)


def ask_gemini(prompt: str) -> str:
    def _call():
        response = _get_gemini_client().models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text

    return _with_retry(_call)


def ask_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    def _call():
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    return _with_retry(_call)


def route_model(provider: str, prompt: str) -> str:
    _enforce_rate_limit(provider)

    if provider == "claude":
        return ask_claude(prompt)
    if provider == "openai":
        return ask_openai(prompt)
    if provider == "gemini":
        return ask_gemini(prompt)
    if provider in {"ollama", "local"}:
        return ask_ollama(prompt)
    raise ValueError(f"Unknown provider: {provider}")
