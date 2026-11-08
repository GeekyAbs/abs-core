"""Ingest portfolio knowledge into SQLite.

Run from anywhere:
    uv run python scripts/ingest.py

Sources default to ``docs/knowledge.md`` and ``docs/knowledge.txt``. Override
with ``KB_PATHS`` (comma-separated files or globs, relative to the backend
directory).
"""

import glob
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.ingest import ingest_documents

DEFAULT_PATHS = ("docs/knowledge.md", "docs/knowledge.txt")


def resolve_paths(spec: str) -> list[Path]:
    paths: list[Path] = []
    for raw in spec.split(","):
        raw = raw.strip()
        if not raw:
            continue
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        matches = (
            sorted(glob.glob(str(candidate)))
            if glob.has_magic(str(candidate))
            else [str(candidate)]
        )
        for match in matches:
            path = Path(match)
            if path.is_file() and path not in paths:
                paths.append(path)
    return paths


def load_docs(paths: list[Path]) -> list[tuple[str, str, str]]:
    docs: list[tuple[str, str, str]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Skipping {path}: {exc}", file=sys.stderr)
            continue
        if not text.strip():
            print(f"Skipping {path}: file is empty", file=sys.stderr)
            continue
        try:
            source = str(path.relative_to(ROOT))
        except ValueError:
            source = str(path)
        docs.append((source, "doc", text))
    return docs


def main() -> int:
    spec = os.getenv("KB_PATHS", ",".join(DEFAULT_PATHS))
    paths = resolve_paths(spec)
    if not paths:
        print(
            "No knowledge files found. Create docs/knowledge.md "
            "(see docs/knowledge.md.example) or set KB_PATHS.",
            file=sys.stderr,
        )
        return 1

    docs = load_docs(paths)
    if not docs:
        print("No readable, non-empty knowledge files.", file=sys.stderr)
        return 1

    try:
        count = ingest_documents(docs)
    except Exception as exc:  # noqa: BLE001 - CLI boundary: report any failure plainly
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Ingested {count} chunks from {len(docs)} file(s) into {os.getenv('DB_PATH', './data/portfolio.db')}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
