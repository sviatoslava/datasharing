"""Lightweight retrieval over the local product knowledge base.

Pure-Python TF-IDF scoring — no embedding model or vector DB — since the corpus is a
handful of short reference documents. This also keeps retrieval fully testable without a
running LLM.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
_WORD_RE = re.compile(r"[a-zA-Z]+")

# Common words carry near-zero topical signal but can still have high IDF (rare enough to
# accidentally decide a close match), so they're stripped before scoring rather than relying
# on IDF weighting alone to suppress them.
_STOPWORDS = frozenset(
    """
    a an the and or but is are was were be been being to of in on at for with about as by
    from into what how why when where who which whose i you your my me we our us it its
    this that these those do does did can could will would should shall may might have has
    had not no so if than then there here s t re ve ll d m
    """.split()
)


def _stem(token: str) -> str:
    # Minimal plural stripping (mortgages -> mortgage, fees -> fee) so a singular query word
    # matches a pluralized doc title/heading. Applied uniformly to query and corpus, so even
    # a linguistically-rough stem is fine as long as it's consistent on both sides.
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    words = _WORD_RE.findall(text.lower())
    return [_stem(t) for t in words if t not in _STOPWORDS and len(t) > 1]


@dataclass
class Chunk:
    title: str
    text: str

    def token_counts(self) -> Counter:
        return Counter(_tokenize(self.title + " " + self.text))

    def title_tokens(self) -> set[str]:
        return set(_tokenize(self.title))


def load_chunks(directory: Path = KNOWLEDGE_DIR) -> list[Chunk]:
    return [
        Chunk(title=path.stem.replace("_", " ").title(), text=path.read_text())
        for path in sorted(directory.glob("*.md"))
    ]


def _build_idf(chunk_counts: list[Counter]) -> dict[str, float]:
    n = len(chunk_counts) or 1
    doc_freq: dict[str, int] = {}
    for counts in chunk_counts:
        for token in counts:
            doc_freq[token] = doc_freq.get(token, 0) + 1
    return {token: math.log((n + 1) / (df + 1)) + 1 for token, df in doc_freq.items()}


# Empirical noise floor for this corpus: a handful of incidentally shared words (e.g. a
# completely off-topic question that happens to share "bank" and "current") score in the
# 0.03-0.045 range, while genuine topic matches score 0.05+ and usually much higher. Below
# this, treat it as "no confident match" rather than grounding the model in a stray chunk.
_MIN_SCORE = 0.045

# A query word matching a chunk's own title (its primary topic) is a much stronger topical
# signal than the same word appearing incidentally in running text, but contributes only one
# small term among a chunk's full token count — so it's boosted directly rather than relying
# on term frequency alone to surface it.
_TITLE_MATCH_BOOST = 0.05


def retrieve(query: str, chunks: list[Chunk] | None = None, k: int = 3) -> list[Chunk]:
    """Return up to k chunks confidently relevant to query, or [] if nothing scores highly
    enough to trust — callers should treat an empty result as "no matching reference material"
    rather than silently falling back to an arbitrary/unrelated chunk."""
    chunks = load_chunks() if chunks is None else chunks
    if not chunks:
        return []

    query_tokens = set(_tokenize(query))
    chunk_counts = [c.token_counts() for c in chunks]
    idf = _build_idf(chunk_counts)

    scored = []
    for chunk, counts in zip(chunks, chunk_counts):
        total = sum(counts.values()) or 1
        score = sum((counts.get(t, 0) / total) * idf.get(t, 0.0) for t in query_tokens)
        score += _TITLE_MATCH_BOOST * len(query_tokens & chunk.title_tokens())
        scored.append((chunk, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [chunk for chunk, score in scored[:k] if score >= _MIN_SCORE]
