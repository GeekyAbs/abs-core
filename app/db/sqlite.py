"""SQLite + sqlite-vec helpers."""

import sqlite3
from pathlib import Path

import sqlite_vec


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection, dim: int) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            section TEXT,
            content TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
            embedding float[{dim}]
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content, content='chunks', content_rowid='id'
        );
        """
    )
    conn.commit()