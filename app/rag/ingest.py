"""Ingestion: text -> chunks -> embeddings -> sqlite."""

from collections.abc import Iterable

from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.db.sqlite import connect, init_schema
from app.rag.chunking import chunk_text


def embedder() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embed_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )


def ingest_documents(docs: Iterable[tuple[str, str, str]], dim: int = 1536) -> int:
    """docs: (source, section, text). Returns number of chunks inserted."""
    conn = connect(settings.db_path)
    init_schema(conn, dim)
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM chunks_vec")
    conn.execute("DELETE FROM chunks_fts")
    conn.commit()

    em = embedder()
    total = 0
    for source, section, text in docs:
        for chunk in chunk_text(text):
            vec = em.embed_query(chunk)
            cur = conn.execute(
                "INSERT INTO chunks(source, section, content) VALUES (?,?,?)",
                (source, section, chunk),
            )
            rid = cur.lastrowid
            conn.execute(
                "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                (rid, _to_blob(vec)),
            )
            conn.execute(
                "INSERT INTO chunks_fts(rowid, content) VALUES (?, ?)",
                (rid, chunk),
            )
            total += 1
    conn.commit()
    conn.close()
    return total


def _to_blob(vec: list[float]) -> bytes:
    import struct

    return struct.pack(f"{len(vec)}f", *vec)