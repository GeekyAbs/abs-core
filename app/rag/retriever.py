"""Hybrid retrieval: vector (sqlite-vec) + FTS5, fused with RRF."""

import logging
import re
import sqlite3
import unicodedata
from pathlib import Path

from app.config import settings
from app.db.sqlite import connect, get_meta
from app.rag.embeddings import build_embedder
from app.rag.ingest import _to_blob

log = logging.getLogger(__name__)

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_RRF_K = 60
_MAX_FTS_TOKENS = 20


class RetrievalUnavailable(RuntimeError):
    """The knowledge base is missing, empty, or incompatible with the model."""


def build_fts_query(text: str) -> str | None:
    """Turn free-form user text into a safe FTS5 expression.

    Raw input is not valid FTS5 syntax: ``?``, ``:``, ``+``, ``@``, ``/``,
    ``-`` and bare ``AND`` all raise OperationalError, which used to surface
    as a 500 on questions as ordinary as "who is abesh?". Each token is
    quoted, so nothing the user types is interpreted as an operator.
    """
    normalised = unicodedata.normalize("NFKC", text).lower()
    tokens = [t for t in _WORD.findall(normalised) if len(t) > 1][:_MAX_FTS_TOKENS]
    if not tokens:
        return None
    return " OR ".join(f'"{t}"' for t in tokens)


def fts_search(conn: sqlite3.Connection, query: str, limit: int) -> list[int]:
    """Return rowids ordered by BM25 relevance (best first)."""
    expression = build_fts_query(query)
    if expression is None:
        return []
    try:
        rows = conn.execute(
            "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
            (expression, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        # A malformed expression should degrade to vector-only search, never
        # take down the request.
        log.warning("fts query rejected: %r", expression, exc_info=True)
        return []
    return [row["rowid"] for row in rows]


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def _load_chunks(conn: sqlite3.Connection, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id, source, section, content FROM chunks WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    by_id = {row["id"]: dict(row) for row in rows}
    return [by_id[rid] for rid in ids if rid in by_id]


def retrieve(
    query: str,
    k: int | None = None,
    *,
    db_path: str | Path | None = None,
    embedder=None,
) -> list[dict]:
    path = Path(db_path or settings.db_path)
    k = k or settings.top_k

    if not path.exists():
        raise RetrievalUnavailable(f"knowledge base not found at {path}; run scripts/ingest.py")

    conn = connect(path)
    try:
        tables = _table_names(conn)
        if not {"chunks", "chunks_vec", "chunks_fts"} <= tables:
            raise RetrievalUnavailable(
                f"knowledge base at {path} has no schema; run scripts/ingest.py"
            )
        if conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0:
            raise RetrievalUnavailable(f"knowledge base at {path} is empty; run scripts/ingest.py")

        query_vector = (embedder or build_embedder()).embed_query(query)
        stored_dim = get_meta(conn).get("dim")
        if stored_dim and int(stored_dim) != len(query_vector):
            raise RetrievalUnavailable(
                f"embedding dimension mismatch: index has {stored_dim}, "
                f"{settings.embed_model} returned {len(query_vector)}; re-run scripts/ingest.py"
            )

        vector_rows = conn.execute(
            "SELECT rowid, distance FROM chunks_vec WHERE embedding MATCH ? "
            "ORDER BY distance LIMIT ?",
            (_to_blob(query_vector), k * 3),
        ).fetchall()
        vector_ids = [
            row["rowid"]
            for row in vector_rows
            if (1.0 - row["distance"]) >= settings.min_similarity
        ]
        keyword_ids = fts_search(conn, query, k * 2)

        scores: dict[int, float] = {}
        for rank, row_id in enumerate(vector_ids):
            scores[row_id] = scores.get(row_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
        for rank, row_id in enumerate(keyword_ids):
            scores[row_id] = scores.get(row_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

        ranked = sorted(scores, key=lambda row_id: scores[row_id], reverse=True)[:k]
        return _load_chunks(conn, ranked)
    finally:
        conn.close()
