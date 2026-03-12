import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Dense embeddings via sentence-transformers (optional).
# Set COUNCIL_DENSE_EMBEDDINGS=0 to force TF-IDF even if the library is installed.
try:
    from sentence_transformers import SentenceTransformer
    _DENSE_AVAILABLE = True
except ImportError:
    _DENSE_AVAILABLE = False

_EMBEDDING_MODEL_NAME = os.environ.get("COUNCIL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_dense_model = None


def _get_dense_model() -> "SentenceTransformer":
    global _dense_model
    if _dense_model is None:
        _dense_model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
    return _dense_model


def _use_dense() -> bool:
    return _DENSE_AVAILABLE and os.environ.get("COUNCIL_DENSE_EMBEDDINGS", "1") == "1"


SUPPORTED_EXTENSIONS = {".md", ".txt", ".json", ".pdf"}


@dataclass
class EvidenceChunk:
    source: str
    text: str


class EvidenceRetriever:
    def __init__(self, chunks: List[EvidenceChunk]):
        self.chunks = chunks
        self._dense = _use_dense() and bool(chunks)

        if self._dense:
            model = _get_dense_model()
            self._embeddings = model.encode([c.text for c in chunks], convert_to_numpy=True)
        elif chunks:
            self._vectorizer = TfidfVectorizer(stop_words="english")
            self._matrix = self._vectorizer.fit_transform([c.text for c in chunks])
        else:
            self._vectorizer = None
            self._matrix = None

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

        if self._dense:
            model = _get_dense_model()
            query_emb = model.encode([query], convert_to_numpy=True)
            scores = cosine_similarity(query_emb, self._embeddings)[0]
        else:
            if self._vectorizer is None:
                return []
            query_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self._matrix)[0]

        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [self.chunks[i] for i in ranked if scores[i] > 0]


def format_evidence_for_prompt(chunks: List[EvidenceChunk]) -> str:
    if not chunks:
        return "No external evidence retrieved."

    return "\n\n---\n\n".join(f"Source: {chunk.source}\n{chunk.text}" for chunk in chunks)


def _read_file(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return json.dumps(data, indent=2)

    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    return ""


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    clean = " ".join(text.split())
    return [clean[i:i + chunk_size] for i in range(0, len(clean), chunk_size)]
