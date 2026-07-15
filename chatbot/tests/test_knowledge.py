"""Tests for the pure-Python keyword retrieval over the product knowledge base."""
from knowledge import Chunk, load_chunks, retrieve


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
    assert retrieve("What's Halyk Bank's current CEO?", chunks=chunks, k=3) == []
    assert retrieve("What's the weather today?", chunks=chunks, k=3) == []


def test_retrieve_returns_empty_list_for_empty_corpus():
    assert retrieve("anything", chunks=[], k=3) == []


def test_retrieve_respects_k():
    chunks = load_chunks()

    assert len(retrieve("account card loan deposit mortgage app", chunks=chunks, k=2)) <= 2
