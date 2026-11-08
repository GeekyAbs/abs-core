"""Hybrid retrieval: vector (sqlite-vec) + FTS5, fused with RRF."""

import struct

from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.db.sqlite import connect


def _blob_to_vec(b: bytes) -> list[float]:
    n = len(b) // 4
    return list(struct.unpack(f"{n}f", b))


def retrieve(query: str, k: int = 5) -> list[dict]:
    conn = connect(settings.db_path)
    em = OpenAIEmbeddings(
        model=settings.embed_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    qvec = em.embed_query(query)
    # vector search
    rows = conn.execute(
        "SELECT rowid, distance FROM chunks_vec WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (_to_blob(qvec), k * 2),
    ).fetchall()
    vec_ids = [r["rowid"] for r in rows]

    # fts search
    fts_rows = conn.execute(
        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT ?",
        (query, k * 2),
    ).fetchall()
    fts_ids = [r["rowid"] for r in fts_rows]

    # RRF
    scores: dict[int, float] = {}
    for rank, rid in enumerate(vec_ids):
        scores[rid] = scores.get(rid, 0) + 1 / (60 + rank + 1)
    for rank, rid in enumerate(fts_ids):
        scores[rid] = scores.get(rid, 0) + 1 / (60 + rank + 1)

    top = sorted(scores, key=lambda r: scores[r], reverse=True)[:k]
    out = []
    for rid in top:
        r = conn.execute(
            "SELECT id, source, section, content FROM chunks WHERE id=?", (rid,)
        ).fetchone()
        if r:
            out.append(dict(r))
    conn.close()
    return out


def _to_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)