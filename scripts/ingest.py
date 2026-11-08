"""Ingest portfolio knowledge into SQLite. Run: uv run python scripts/ingest.py"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.ingest import ingest_documents

DOCS = ["docs/knowledge.md", "docs/knowledge.txt"]


def load_docs():
    out = []
    for p in DOCS:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                out.append(("portfolio", "all", f.read()))
    # also any md in docs/
    for p in glob.glob("docs/*.md"):
        if p not in DOCS and not p.endswith("README.md"):
            with open(p, encoding="utf-8") as f:
                out.append((os.path.basename(p), "doc", f.read()))
    return out


def main():
    docs = load_docs()
    if not docs:
        print("No docs found. Create docs/knowledge.md (gitignored) with your portfolio info.")
        return 1
    n = ingest_documents(docs)
    print(f"Ingested {n} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())