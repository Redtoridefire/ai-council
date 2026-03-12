import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


SUPPORTED_EXTENSIONS = {".md", ".txt", ".json", ".pdf"}


@dataclass
class EvidenceChunk:
    source: str
    text: str


class EvidenceRetriever:
    def __init__(self, chunks: List[EvidenceChunk]):
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform([c.text for c in chunks]) if chunks else None

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
        return bool(self.chunks) and self.matrix is not None

    def retrieve(self, query: str, top_k: int = 4) -> List[EvidenceChunk]:
        if not self.has_evidence():
            return []

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix)[0]

        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [self.chunks[i] for i in ranked_indices if scores[i] > 0]


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
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    return ""


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    clean = " ".join(text.split())
    return [clean[i:i + chunk_size] for i in range(0, len(clean), chunk_size)]
