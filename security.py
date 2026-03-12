import hashlib
import re
from typing import Any, Dict


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"xoxb-[0-9A-Za-z-]{20,}"),
]


def redact_sensitive_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def pseudonymize_text(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"hash:{digest}"


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {}
    for key, value in metadata.items():
        if value is None:
            cleaned[key] = None
        elif isinstance(value, str):
            cleaned[key] = redact_sensitive_text(value)
        else:
            cleaned[key] = value
    return cleaned
