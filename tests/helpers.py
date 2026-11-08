"""Shared test helpers. Test-only code stays out of the production package."""

from app.db.sqlite import connect, init_schema
from app.rag.ingest import _to_blob


class FakeEmbedder:
    """Deterministic stand-in for OpenAIEmbeddings.

    Every text embeds to the same unit vector, so every row is equidistant
    unless a test seeds explicit vectors. ``dim`` controls the schema size.
    """

    def __init__(self, dim: int = 4, fail_on_call: int | None = None):
        self.dim = dim
        self.calls = 0
        self.fail_on_call = fail_on_call

    def _vector(self) -> list[float]:
        self.calls += 1
        if self.fail_on_call is not None and self.calls >= self.fail_on_call:
            raise RuntimeError("embedding provider unavailable")
        return [1.0] + [0.0] * (self.dim - 1)

    def embed_query(self, text: str) -> list[float]:
        return self._vector()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector() for _ in texts]


def seed_db(db_path: str, embedder: FakeEmbedder, rows: list[tuple[str, str, str]] | None = None):
    """Create a schema and insert a few chunks with identical vectors."""
    rows = rows or [
        ("portfolio", "experience", "Abesh Chakraborty is an AI/ML engineer in Kolkata."),
        ("blog", "projects", "He built a ten endpoint FastAPI service with live streaming."),
    ]
    conn = connect(db_path)
    init_schema(conn, embedder.dim, embed_model="test-model", recreate=True)
    for row_id, (source, section, content) in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO chunks(id, source, section, content) VALUES (?, ?, ?, ?)",
            (row_id, source, section, content),
        )
        conn.execute(
            "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
            (row_id, _to_blob([1.0] + [0.0] * (embedder.dim - 1))),
        )
        conn.execute(
            "INSERT INTO chunks_fts(rowid, content) VALUES (?, ?)",
            (row_id, content),
        )
    conn.commit()
    conn.close()
