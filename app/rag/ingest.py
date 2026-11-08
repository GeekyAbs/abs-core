"""Ingestion: text -> chunks -> embeddings -> sqlite."""

import logging
import os
import struct
from collections.abc import Iterable
from pathlib import Path

from app.config import settings
from app.db.sqlite import connect, init_schema
from app.rag.chunking import chunk_text
from app.rag.embeddings import build_embedder

log = logging.getLogger(__name__)


def ingest_documents(
    docs: Iterable[tuple[str, str, str]],
    *,
    db_path: str | Path | None = None,
    embedder=None,
    batch_size: int = 64,
) -> int:
    """Build the knowledge base and atomically swap it into place.

    ``docs`` is ``(source, section, text)``. The new database is written next
    to the target and moved over it only after every chunk is embedded, so a
    provider error cannot leave a live deployment with an empty corpus.
    """
    documents = list(docs)
    if not documents:
        raise ValueError("no documents to ingest")

    rows: list[tuple[str, str, str]] = []
    for source, section, text in documents:
        for chunk in chunk_text(text):
            rows.append((source, section, chunk))
    if not rows:
        raise ValueError("documents produced no chunks")

    target = Path(db_path or settings.db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    building = target.with_name(target.name + ".building")
    _remove_sqlite_files(building)

    em = embedder or build_embedder()
    conn = None
    try:
        probe = em.embed_query("dimension probe")
        dim = len(probe)
        if dim == 0:
            raise ValueError("embedding model returned an empty vector")

        vectors: list[list[float]] = []
        for start in range(0, len(rows), batch_size):
            batch = [row[2] for row in rows[start : start + batch_size]]
            embedded = em.embed_documents(batch)
            if len(embedded) != len(batch):
                raise RuntimeError(
                    f"embedding model returned {len(embedded)} vectors for {len(batch)} chunks"
                )
            vectors.extend(embedded)

        conn = connect(building)
        init_schema(conn, dim, embed_model=settings.embed_model, recreate=True)
        with conn:
            for (source, section, content), vector in zip(rows, vectors, strict=True):
                cursor = conn.execute(
                    "INSERT INTO chunks(source, section, content) VALUES (?, ?, ?)",
                    (source, section, content),
                )
                row_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                    (row_id, _to_blob(vector)),
                )
                conn.execute(
                    "INSERT INTO chunks_fts(rowid, content) VALUES (?, ?)",
                    (row_id, content),
                )
        conn.close()
        conn = None

        os.replace(building, target)
        log.info("ingested %d chunks into %s (dim=%d)", len(rows), target, dim)
        return len(rows)
    except Exception:
        if conn is not None:
            conn.close()
        _remove_sqlite_files(building)
        raise


def _remove_sqlite_files(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)


def _to_blob(vec: list[float]) -> bytes:
    # sqlite-vec expects little-endian float32 regardless of host byte order.
    return struct.pack(f"<{len(vec)}f", *vec)
