#!/usr/bin/env python3
"""
test_mavis_rag_hybrid — Unit tests for mavis-rag BM25 + RRF hybrid search.

Validates:
- BM25 score function returns > 0 for matching terms
- BM25 score returns 0 for non-matching terms
- _hybrid_search returns fused list, sorted by RRF desc
- _hybrid_search handles empty input gracefully
- _tokenize is deterministic and lowercase
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "mavis_rag",
    Path(__file__).parent.parent / "scripts" / "mavis-rag.py",
)
mavis_rag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mavis_rag)


def test_tokenize_lowercases_and_splits():
    tokens = mavis_rag._tokenize("Hello World! Foo_Bar 123")
    assert all(t == t.lower() for t in tokens)
    assert "hello" in tokens
    assert "world" in tokens
    assert "foo_bar" in tokens
    # Numbers split, but length filter keeps ≥ 2 char tokens
    assert "123" in tokens


def test_tokenize_drops_short_tokens():
    tokens = mavis_rag._tokenize("a b c d ef")
    assert "a" not in tokens
    assert "ef" in tokens


def test_bm25_score_matching_terms():
    score = mavis_rag._bm25_score("OAuth pool unlock", "OAuth pool unlock trick with beta header")
    assert score > 0


def test_bm25_score_no_match():
    score = mavis_rag._bm25_score("xyzzy", "OAuth pool unlock trick with beta header")
    assert score == 0.0


def test_bm25_score_empty_query():
    score = mavis_rag._bm25_score("", "some content here")
    assert score == 0.0


def test_bm25_score_empty_doc():
    score = mavis_rag._bm25_score("OAuth", "")
    assert score == 0.0


def test_hybrid_search_returns_fused_list():
    query = "OAuth pool"
    qvec = [0.0] * 10  # dummy vector
    chunks = [
        {"id": 1, "content": "OAuth pool unlock with beta header", "embedding": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
        {"id": 2, "content": "unrelated content about cats", "embedding": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
        {"id": 3, "content": "OAuth and authentication flow", "embedding": [0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
    ]
    result = mavis_rag._hybrid_search(query, qvec, chunks, top_k=3)
    assert len(result) == 3
    # All entries are (rrf, chunk, dense_score, bm25_score)
    for rrf, chunk, dense, bm25 in result:
        assert isinstance(rrf, float)
        assert isinstance(chunk, dict)
    # First entry has highest rrf score
    assert result[0][0] >= result[1][0] >= result[2][0]


def test_hybrid_search_handles_string_embedding():
    """Old Supabase rows store embedding as a JSON string. Ensure we handle it."""
    import json
    query = "OAuth"
    qvec = [0.0] * 4
    chunks = [
        {"id": 1, "content": "OAuth pool", "embedding": json.dumps([1.0, 0.0, 0.0, 0.0])},
    ]
    result = mavis_rag._hybrid_search(query, qvec, chunks, top_k=1)
    assert len(result) == 1


def test_hybrid_search_empty_corpus():
    result = mavis_rag._hybrid_search("test", [0.0] * 4, [], top_k=5)
    assert result == []


def test_hybrid_search_top_k_respected():
    qvec = [0.0] * 4
    chunks = [{"id": i, "content": f"doc {i}", "embedding": [float(i), 0.0, 0.0, 0.0]} for i in range(10)]
    result = mavis_rag._hybrid_search("doc", qvec, chunks, top_k=3)
    assert len(result) == 3
