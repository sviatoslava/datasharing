"""Lightweight retrieval over the local product knowledge base.

Pure-Python keyword/TF-IDF scoring — no embedding model or vector DB — since the corpus is a
handful of short reference documents. This also keeps retrieval fully testable without a
running LLM.
"""
import math
import re
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
_WORD_RE = re.compile(r"[a-zA-Z]+")


@dataclass
class Chunk:
    title: str
    text: str

    def tokens(self) -> set[str]:
        return set(_WORD_RE.findall((self.title + " " + self.text).lower()))


def load_chunks(directory: Path = KNOWLEDGE_DIR) -> list[Chunk]:
    return [
        Chunk(title=path.stem.replace("_", " ").title(), text=path.read_text())
        for path in sorted(directory.glob("*.md"))
    ]


def _build_idf(chunks: list[Chunk]) -> dict[str, float]:
    n = len(chunks) or 1
    doc_freq: dict[str, int] = {}
    for chunk in chunks:
        for token in chunk.tokens():
            doc_freq[token] = doc_freq.get(token, 0) + 1
    return {token: math.log((n + 1) / (count + 1)) + 1 for token, count in doc_freq.items()}


def retrieve(query: str, chunks: list[Chunk] | None = None, k: int = 3) -> list[Chunk]:
    chunks = load_chunks() if chunks is None else chunks
    if not chunks:
        return []

    query_tokens = set(_WORD_RE.findall(query.lower()))
    idf = _build_idf(chunks)
    scored = [
        (chunk, sum(idf.get(token, 0.0) for token in query_tokens & chunk.tokens()))
        for chunk in chunks
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    top = [chunk for chunk, score in scored[:k] if score > 0]
    return top or chunks[:1]  # no keyword match at all — fall back to something rather than nothing
