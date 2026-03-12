import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple



SUPPORTED_EXTENSIONS = {".md", ".txt", ".json", ".pdf"}
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]{2,}")


@dataclass
class EvidenceChunk:
    source: str
    text: str


class EvidenceRetriever:
    def __init__(self, chunks: List[EvidenceChunk]):
        self.chunks = chunks
        self._chunk_vectors: List[Counter] = [_tokenize_counter(c.text) for c in chunks]
        self._chunk_norms: List[float] = [_counter_norm(v) for v in self._chunk_vectors]

    @classmethod
    def from_docs_dir(cls, docs_dir: str = "docs", chunk_size: int = 1200) -> "EvidenceRetriever":
        docs_path = Path(docs_dir)
        chunks: List[EvidenceChunk] = []

        if not docs_path.exists() or not docs_path.is_dir():
            return cls(chunks)

        for path in sorted(docs_path.iterdir()):
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS or not path.is_file():
                continue

            text = _read_file(path)
            if not text.strip():
                continue

            for idx, piece in enumerate(_chunk_text(text, chunk_size)):
                chunks.append(EvidenceChunk(source=f"{path}#chunk-{idx + 1}", text=piece))

        return cls(chunks)

    def has_evidence(self) -> bool:
        return bool(self.chunks)

    def retrieve(self, query: str, top_k: int = 4) -> List[EvidenceChunk]:
        if not self.has_evidence():
            return []

        query_vec = _tokenize_counter(query)
        query_norm = _counter_norm(query_vec)
        if query_norm == 0:
            return []

        scored: List[Tuple[int, float]] = []
        for idx, chunk_vec in enumerate(self._chunk_vectors):
            score = _cosine_similarity(query_vec, query_norm, chunk_vec, self._chunk_norms[idx])
            if score > 0:
                scored.append((idx, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [self.chunks[idx] for idx, _ in scored[:top_k]]


def format_evidence_for_prompt(chunks: List[EvidenceChunk]) -> str:
    if not chunks:
        return "No external evidence retrieved."

    formatted = []
    for chunk in chunks:
        formatted.append(f"Source: {chunk.source}\n{chunk.text}")

    return "\n\n---\n\n".join(formatted)


def _read_file(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return json.dumps(data, indent=2)

    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    return ""


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    clean = " ".join(text.split())
    return [clean[i:i + chunk_size] for i in range(0, len(clean), chunk_size)]


def _tokenize_counter(text: str) -> Counter:
    return Counter(token.lower() for token in _TOKEN_RE.findall(text))


def _counter_norm(counter: Counter) -> float:
    return math.sqrt(sum(v * v for v in counter.values()))


def _cosine_similarity(a: Counter, a_norm: float, b: Counter, b_norm: float) -> float:
    if a_norm == 0 or b_norm == 0:
        return 0.0
    dot = sum(a[t] * b.get(t, 0) for t in a)
    return dot / (a_norm * b_norm)
