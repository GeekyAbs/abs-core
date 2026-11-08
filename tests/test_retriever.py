import pytest

from app.config import settings
from app.db.sqlite import connect, init_schema
from app.rag.ingest import _to_blob
from app.rag.retriever import (
    RetrievalUnavailable,
    build_fts_query,
    fts_search,
    retrieve,
)
from tests.helpers import FakeEmbedder


def test_build_fts_query_quotes_every_token():
    assert build_fts_query("who is abesh?") == '"who" OR "is" OR "abesh"'


def test_build_fts_query_returns_none_for_punctuation_only():
    assert build_fts_query("C++ ?") is None


@pytest.mark.parametrize(
    "query",
    [
        "who is abesh?",
        "What's his email?",
        "skills: python",
        "C++ experience",
        "hello?",
        "ai/ml engineer",
        "contact me at x@y.com",
        "*",
        "AND",
    ],
)
def test_retrieve_survives_fts_syntax_characters(seeded_db, embedder, query):
    """Regression: FTS5 used to raise OperationalError, turning /chat into a 500."""
    results = retrieve(query, db_path=seeded_db, embedder=embedder)

    assert isinstance(results, list)


def test_retrieve_raises_when_database_missing(db_path, embedder):
    with pytest.raises(RetrievalUnavailable, match="not found"):
        retrieve("who is abesh", db_path=db_path, embedder=embedder)


def test_retrieve_raises_when_corpus_is_empty(db_path, embedder):
    conn = connect(db_path)
    init_schema(conn, embedder.dim, embed_model="test-model", recreate=True)
    conn.close()

    with pytest.raises(RetrievalUnavailable, match="empty"):
        retrieve("who is abesh", db_path=db_path, embedder=embedder)


def test_retrieve_raises_on_embedding_dimension_mismatch(seeded_db):
    wrong_size = FakeEmbedder(dim=8)

    with pytest.raises(RetrievalUnavailable, match="dimension"):
        retrieve("abesh", db_path=seeded_db, embedder=wrong_size)


def test_retrieve_drops_candidates_below_similarity_threshold(db_path, monkeypatch):
    dim = 4
    conn = connect(db_path)
    init_schema(conn, dim, embed_model="test-model", recreate=True)
    # Orthogonal to the query vector: cosine similarity 0.
    conn.execute(
        "INSERT INTO chunks(id, source, section, content) VALUES (1, 's', 'x', 'unrelated text')"
    )
    conn.execute(
        "INSERT INTO chunks_vec(rowid, embedding) VALUES (1, ?)", (_to_blob([0, 1, 0, 0]),)
    )
    conn.execute("INSERT INTO chunks_fts(rowid, content) VALUES (1, 'unrelated text')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(settings, "min_similarity", 0.9)
    results = retrieve("zzz", db_path=db_path, embedder=FakeEmbedder(dim=dim))

    assert results == []


def test_fts_search_orders_by_bm25(db_path):
    conn = connect(db_path)
    init_schema(conn, 4, embed_model="test-model", recreate=True)
    docs = [
        ("strong", "fastapi fastapi fastapi service"),
        ("weak", "fastapi service"),
        ("none", "docker compose"),
    ]
    for row_id, (_, content) in enumerate(docs, start=1):
        conn.execute(
            "INSERT INTO chunks(id, source, section, content) VALUES (?, 's', 'x', ?)",
            (row_id, content),
        )
        conn.execute("INSERT INTO chunks_fts(rowid, content) VALUES (?, ?)", (row_id, content))
    conn.commit()

    ordered = fts_search(conn, "fastapi", limit=3)
    conn.close()

    assert ordered[0] == 1
    assert set(ordered) == {1, 2}


def test_retrieve_returns_content_and_source(seeded_db, embedder):
    results = retrieve("Abesh engineer", db_path=seeded_db, embedder=embedder)

    assert results
    assert {"id", "source", "section", "content"} <= set(results[0])
