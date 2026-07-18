"""Tests for the pure-Python keyword retrieval over the product knowledge base."""
from knowledge import Chunk, is_ambiguous, load_chunks, retrieve, retrieve_scored, retrieve_semantic


class FakeEmbedder:
    """Deterministic bag-of-words embedder for testing retrieve_semantic() without a real
    model: shared vocabulary words become shared vector dimensions, so cosine similarity
    behaves predictably. Counts calls so tests can verify the embedding cache works."""

    _VOCAB = ["loan", "mortgage", "cat", "card", "deposit"]

    def __init__(self):
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        words = text.lower().split()
        return [float(words.count(w)) for w in self._VOCAB]


def test_load_chunks_finds_all_knowledge_files():
    chunks = load_chunks()
    titles = {c.title for c in chunks}
    assert {"Cards", "Deposits", "Loans", "Mortgages", "Mobile App"} <= titles


def test_retrieve_ranks_the_relevant_chunk_first():
    chunks = load_chunks()

    top = retrieve("what's the interest rate on a mortgage for a house", chunks=chunks, k=1)

    assert top[0].title == "Mortgages"


def test_retrieve_disambiguates_similar_topics():
    chunks = load_chunks()

    assert retrieve("term deposit interest rate", chunks=chunks, k=1)[0].title == "Deposits"
    assert retrieve("credit card cashback rewards", chunks=chunks, k=1)[0].title == "Cards"
    assert retrieve("personal loan for a renovation", chunks=chunks, k=1)[0].title == "Loans"


def test_retrieve_returns_empty_on_no_keyword_overlap():
    chunks = [Chunk(title="Only Topic", text="banana banana banana")]

    result = retrieve("completely unrelated gibberish query", chunks=chunks, k=3)

    assert result == []


def test_retrieve_returns_empty_for_genuinely_out_of_scope_query():
    chunks = load_chunks()

    # shares only generic/incidental words with the corpus, no real topical match
    assert retrieve("What's the bank's current CEO?", chunks=chunks, k=3) == []
    assert retrieve("What's the weather today?", chunks=chunks, k=3) == []


def test_retrieve_returns_empty_list_for_empty_corpus():
    assert retrieve("anything", chunks=[], k=3) == []


def test_retrieve_respects_k():
    chunks = load_chunks()

    assert len(retrieve("account card loan deposit mortgage app", chunks=chunks, k=2)) <= 2


def test_retrieve_scored_matches_retrieve():
    chunks = load_chunks()
    query = "credit card cashback rewards"

    assert [c for c, _ in retrieve_scored(query, chunks=chunks)] == retrieve(query, chunks=chunks)


def test_no_false_positive_ambiguity_on_the_real_corpus():
    # These all have one clearly-intended topic despite a weaker incidental secondary match
    # (e.g. "account" appears in both Deposits and Mobile App) — none should trigger a
    # clarification prompt.
    chunks = load_chunks()
    clear_queries = [
        "What's the difference between a savings account and a term deposit?",
        "How do I open a savings account?",
        "what's the interest rate on a mortgage for a house",
        "Tell me about credit card rewards",
        "tell me about account security",
    ]
    for query in clear_queries:
        assert not is_ambiguous(retrieve_scored(query, chunks=chunks)), query


def test_is_ambiguous_true_for_close_scores():
    a, b = Chunk(title="A", text="a"), Chunk(title="B", text="b")
    assert is_ambiguous([(a, 0.10), (b, 0.09)]) is True  # ratio ~1.11


def test_is_ambiguous_false_for_a_dominant_top_score():
    a, b = Chunk(title="A", text="a"), Chunk(title="B", text="b")
    assert is_ambiguous([(a, 0.20), (b, 0.05)]) is False  # ratio 4.0


def test_is_ambiguous_false_with_fewer_than_two_candidates():
    a = Chunk(title="A", text="a")
    assert is_ambiguous([]) is False
    assert is_ambiguous([(a, 0.1)]) is False


def test_retrieve_semantic_ranks_by_cosine_similarity():
    embedder = FakeEmbedder()
    chunks = [Chunk(title="Loans", text="loan loan loan"), Chunk(title="Pets", text="cat cat cat")]

    result = retrieve_semantic("loan", embedder, chunks=chunks, k=2, min_score=0.01)

    assert result[0][0].title == "Loans"


def test_retrieve_semantic_filters_below_min_score():
    embedder = FakeEmbedder()
    chunks = [Chunk(title="Pets", text="cat cat cat")]  # zero vocabulary overlap with "loan"

    result = retrieve_semantic("loan", embedder, chunks=chunks, min_score=0.01)

    assert result == []


def test_retrieve_semantic_returns_empty_for_empty_corpus():
    assert retrieve_semantic("anything", FakeEmbedder(), chunks=[], k=3) == []


def test_retrieve_semantic_caches_embeddings_across_calls():
    embedder = FakeEmbedder()
    chunks = [Chunk(title="Loans", text="loan loan loan")]

    retrieve_semantic("loan", embedder, chunks=chunks, min_score=0.0)
    calls_after_first = embedder.calls
    assert calls_after_first > 0

    retrieve_semantic("loan", embedder, chunks=chunks, min_score=0.0)

    # same embedder, same query text, same chunk text — both should hit cache, no new calls
    assert embedder.calls == calls_after_first
