import os
import time
from typing import Callable, Optional

import anthropic

MODEL_AGENT = "claude-haiku-4-5-20251001"
MODEL_CHAIR = "claude-sonnet-4-6"

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def ask_claude(
    prompt: str,
    model: str = MODEL_AGENT,
    max_tokens: int = 800,
    stream_callback: Optional[Callable[[str], None]] = None,
    max_retries: int = 3,
) -> str:
    """
    Call Claude. If stream_callback is provided, tokens are yielded to it as they
    arrive AND the full text is still returned. Retries up to max_retries times
    with exponential backoff on transient errors.
    """
    delay = 2
    for attempt in range(max_retries + 1):
        try:
            if stream_callback is not None:
                full_text = ""
                with client.messages.stream(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    for text in stream.text_stream:
                        stream_callback(text)
                        full_text += text
                return full_text
            else:
                message = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                return message.content[0].text
        except Exception:
            if attempt == max_retries:
                raise
            time.sleep(delay)
            delay *= 2
