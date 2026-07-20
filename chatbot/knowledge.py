"""Lightweight retrieval over the local product knowledge base.

Pure-Python TF-IDF scoring — no embedding model or vector DB — since the corpus is a
handful of short reference documents. This also keeps retrieval fully testable without a
running LLM.
"""
import difflib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
OPTIONS_FILE = KNOWLEDGE_DIR / "options.json"
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


# TF-IDF/cosine matching are both exact-token matching underneath — a single misspelled word
# ("morgage" for "mortgage") produces a token that appears nowhere in the corpus, contributing
# zero signal. If that word was the query's only topic-anchor, retrieval finds nothing at all,
# even though a human reads the question just fine. _correct_spelling fixes this by nudging
# query words toward the *closest word actually in this knowledge base* — not a generic
# dictionary, so it only ever "corrects" toward something meaningfully present here.
#
# Calibrated against real typos vs. real near-miss word pairs (see tests/test_knowledge.py):
# genuine typos of words 4+ chars score a difflib ratio of ~0.85-0.93 ("morgage"~"mortgage"
# 0.93, "fes"~"fees" 0.86), while unrelated same-length words (e.g. "rate"~"rare", "loan"~
# "loam") tie right at 0.75 — so 0.84 catches real typos without those false positives. Words
# of 2 chars or fewer are skipped entirely (too short for the ratio to mean anything).
_SPELL_CORRECTION_CUTOFF = 0.84


def _build_vocabulary(chunks: list) -> set[str]:
    vocabulary: set[str] = set()
    for chunk in chunks:
        vocabulary.update(_WORD_RE.findall((chunk.title + " " + chunk.text).lower()))
    return vocabulary


def _correct_spelling(query: str, vocabulary: set[str]) -> str:
    corrected_words = []
    for raw_word in query.split():
        bare_matches = _WORD_RE.findall(raw_word.lower())
        word = bare_matches[0] if bare_matches else ""
        if not word or len(word) <= 2 or word in _STOPWORDS or word in vocabulary:
            corrected_words.append(raw_word)
            continue
        match = difflib.get_close_matches(word, vocabulary, n=1, cutoff=_SPELL_CORRECTION_CUTOFF)
        corrected_words.append(match[0] if match else raw_word)
    return " ".join(corrected_words)


@dataclass
class Chunk:
    title: str
    text: str

    def token_counts(self) -> Counter:
        return Counter(_tokenize(self.title + " " + self.text))

    def title_tokens(self) -> set[str]:
        return set(_tokenize(self.title))

    @property
    def topic_key(self) -> str:
        # Inverse of load_chunks()'s title derivation (path.stem.replace("_", " ").title()),
        # so a retrieved chunk maps back to its options.json key without re-deriving it twice.
        return self.title.lower().replace(" ", "_")


def load_chunks(directory: Path = KNOWLEDGE_DIR) -> list[Chunk]:
    return [
        Chunk(title=path.stem.replace("_", " ").title(), text=path.read_text())
        for path in sorted(directory.glob("*.md"))
    ]


def get_chunk(topic_key: str, chunks: list[Chunk] | None = None) -> Chunk | None:
    """Look up a chunk by its topic_key directly, bypassing scoring — used to force a specific
    topic (e.g. after the user resolves an ambiguous-match clarification) rather than trusting
    retrieve() to land on it again from text alone."""
    chunks = load_chunks() if chunks is None else chunks
    return next((c for c in chunks if c.topic_key == topic_key), None)


def load_recommended_options(topic_key: str) -> list[dict] | None:
    """Curated follow-up options for a topic (or "fallback" for no confident match), from
    options.json — see that file for the fields each entry accepts. Returns None if the file
    is missing or has no entry for topic_key, so callers can fall back to model-generated
    options rather than showing nothing."""
    if not OPTIONS_FILE.exists():
        return None
    all_options = json.loads(OPTIONS_FILE.read_text())
    return all_options.get(topic_key)


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

# Empirically, queries with one clear intended topic score their top match at 1.4x+ the
# runner-up even when a second chunk also incidentally clears _MIN_SCORE (e.g. "savings
# account" -> Deposits 1.43x Mobile App, both mentioning "account"). Below that ratio, the top
# two are genuinely too close to call — worth asking rather than guessing.
_AMBIGUITY_RATIO = 1.4


def retrieve_scored(query: str, chunks: list[Chunk] | None = None, k: int = 3) -> list[tuple[Chunk, float]]:
    """Like retrieve(), but also returns each chunk's score so callers can judge confidence —
    e.g. via is_ambiguous() — rather than just taking the ranked list at face value."""
    chunks = load_chunks() if chunks is None else chunks
    if not chunks:
        return []

    query = _correct_spelling(query, _build_vocabulary(chunks))
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

    return [(chunk, score) for chunk, score in scored[:k] if score >= _MIN_SCORE]


def retrieve(query: str, chunks: list[Chunk] | None = None, k: int = 3) -> list[Chunk]:
    """Return up to k chunks confidently relevant to query, or [] if nothing scores highly
    enough to trust — callers should treat an empty result as "no matching reference material"
    rather than silently falling back to an arbitrary/unrelated chunk."""
    return [chunk for chunk, _ in retrieve_scored(query, chunks, k)]


def is_ambiguous(scored: list[tuple[Chunk, float]]) -> bool:
    """True when the top two scored candidates (from retrieve_scored) are too close together
    to confidently pick one — the caller should ask the user to disambiguate instead of
    guessing or silently blending both into one answer.

    NOTE: _AMBIGUITY_RATIO was calibrated against retrieve_scored()'s TF-IDF score
    distribution specifically. It has NOT been validated against retrieve_semantic()'s cosine
    similarity scores, which cluster very differently (unrelated documents from the same
    embedding model often still score 0.3-0.5+) — don't feed semantic scores into this
    function without recalibrating the threshold first."""
    if len(scored) < 2:
        return False
    top_score, second_score = scored[0][1], scored[1][1]
    return second_score > 0 and (top_score / second_score) < _AMBIGUITY_RATIO


# --- Optional semantic retrieval -------------------------------------------------------
#
# Opt-in alternative to the TF-IDF scorer above, using a real embedding model (e.g. Ollama's
# nomic-embed-text via langchain_ollama.OllamaEmbeddings) for cosine-similarity matching
# instead of keyword overlap — catches paraphrases that share no common words (e.g. "monthly
# cost" ~ "fee"), which TF-IDF fundamentally cannot.
#
# CAVEAT: this sandbox has no network access to Ollama, so this code is unit-tested against a
# fake embedder (proving the cosine-similarity math, caching, and ranking are correct) but has
# NOT been integration-tested against a real embedding model. _MIN_SEMANTIC_SCORE below is an
# unverified starting point (0.5 is a commonly-cited rough threshold for "relevant" with many
# sentence-embedding models) — treat it as something to tune against your own model and
# knowledge base, not a calibrated constant like _MIN_SCORE/_AMBIGUITY_RATIO above.

_MIN_SEMANTIC_SCORE = 0.5  # UNVERIFIED — tune against your embedding model before relying on it

_embedding_cache: dict[tuple[int, str], list[float]] = {}


def _embed_cached(embedder, text: str) -> list[float]:
    # Keyed by embedder identity + text: the knowledge base is static within a process, so
    # re-embedding the same 5 documents on every single user turn would be a wasted network
    # round-trip each time. Query text isn't cached (always distinct per turn) but chunk text
    # is, which is where the real savings are.
    key = (id(embedder), text)
    if key not in _embedding_cache:
        _embedding_cache[key] = embedder.embed_query(text)
    return _embedding_cache[key]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def retrieve_semantic(
    query: str,
    embedder,
    chunks: list[Chunk] | None = None,
    k: int = 3,
    min_score: float = _MIN_SEMANTIC_SCORE,
) -> list[tuple[Chunk, float]]:
    """Like retrieve_scored(), but via embedding cosine similarity instead of TF-IDF.

    `embedder` is anything exposing `.embed_query(text) -> list[float]` — e.g. a
    langchain_core.embeddings.Embeddings instance such as OllamaEmbeddings(model=...), or (for
    tests) a stand-in exposing the same method. See the module-level caveat above: min_score
    is unverified against any real model."""
    chunks = load_chunks() if chunks is None else chunks
    if not chunks:
        return []

    query = _correct_spelling(query, _build_vocabulary(chunks))
    query_vec = _embed_cached(embedder, query)
    scored = [
        (chunk, _cosine_similarity(query_vec, _embed_cached(embedder, f"{chunk.title}\n{chunk.text}")))
        for chunk in chunks
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [(chunk, score) for chunk, score in scored[:k] if score >= min_score]
