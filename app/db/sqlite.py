"""SQLite + sqlite-vec helpers."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import sqlite_vec

SCHEMA_METRIC = "cosine"


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with sqlite-vec loaded and sane pragmas."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_schema(
    conn: sqlite3.Connection,
    dim: int,
    *,
    embed_model: str | None = None,
    recreate: bool = False,
) -> None:
    """Create (or rebuild) the chunk store.

    ``recreate`` drops the vector table as well, which is required when the
    embedding dimension or distance metric changes: sqlite-vec fixes both at
    CREATE TABLE time and silently ignores later inserts of the wrong width.
    """
    if recreate:
        conn.executescript(
            """
            DROP TABLE IF EXISTS chunks_fts;
            DROP TABLE IF EXISTS chunks_vec;
            DROP TABLE IF EXISTS chunks;
            DROP TABLE IF EXISTS meta;
            """
        )

    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            section TEXT,
            content TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
            embedding float[{int(dim)}] distance_metric={SCHEMA_METRIC}
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content, content='chunks', content_rowid='id'
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    if embed_model is not None:
        for key, value in {
            "embed_model": embed_model,
            "dim": str(int(dim)),
            "metric": SCHEMA_METRIC,
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }.items():
            conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
    conn.commit()


def get_meta(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = conn.execute("SELECT key, value FROM meta").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {row["key"]: row["value"] for row in rows}
