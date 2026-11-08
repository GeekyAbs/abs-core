from pathlib import Path

import pytest

from app.config import settings
from app.db.sqlite import connect, get_meta
from app.rag.ingest import ingest_documents
from app.rag.retriever import retrieve
from tests.helpers import FakeEmbedder

DOCS = [
    ("portfolio", "experience", "Abesh is an AI/ML engineer."),
    ("blog", "projects", "He built a FastAPI service with live streaming."),
]


def test_ingest_writes_chunks_and_metadata(db_path):
    inserted = ingest_documents(DOCS, db_path=db_path, embedder=FakeEmbedder(dim=4))

    conn = connect(db_path)
    chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    meta = get_meta(conn)
    conn.close()

    assert inserted == 2
    assert chunks == 2
    assert meta["dim"] == "4"
    assert meta["embed_model"] == settings.embed_model


def test_reingest_with_a_new_dimension_rebuilds_the_schema(db_path):
    ingest_documents(DOCS, db_path=db_path, embedder=FakeEmbedder(dim=4))
    ingest_documents(DOCS, db_path=db_path, embedder=FakeEmbedder(dim=8))

    conn = connect(db_path)
    meta = get_meta(conn)
    conn.close()

    assert meta["dim"] == "8"
    assert retrieve("engineer", db_path=db_path, embedder=FakeEmbedder(dim=8))


def test_failed_ingest_leaves_the_existing_corpus_queryable(db_path):
    ingest_documents(DOCS, db_path=db_path, embedder=FakeEmbedder(dim=4))

    with pytest.raises(RuntimeError, match="unavailable"):
        ingest_documents(
            [("x", "y", "new content")],
            db_path=db_path,
            embedder=FakeEmbedder(dim=4, fail_on_call=2),
        )

    assert retrieve("engineer", db_path=db_path, embedder=FakeEmbedder(dim=4))


def test_failed_ingest_cleans_up_the_building_file(db_path):
    with pytest.raises(RuntimeError):
        ingest_documents(
            DOCS,
            db_path=db_path,
            embedder=FakeEmbedder(dim=4, fail_on_call=2),
        )

    assert not Path(db_path + ".building").exists()
    assert not Path(db_path).exists()


def test_empty_document_list_raises(db_path):
    with pytest.raises(ValueError, match="no documents"):
        ingest_documents([], db_path=db_path, embedder=FakeEmbedder())


def test_blank_documents_raise(db_path):
    with pytest.raises(ValueError, match="no chunks"):
        ingest_documents([("s", "x", "   \n  ")], db_path=db_path, embedder=FakeEmbedder())
