# Docs

Place your personal portfolio knowledge in `docs/knowledge.md` (gitignored) — experience, projects, skills, contact, etc. Then run:

    uv run python scripts/ingest.py

This builds `data/portfolio.db`. Docker compose mounts `./data` and `./docs`, so the db persists.

A template is provided as `docs/knowledge.md.example`. Copy it to `docs/knowledge.md` and fill in your info. Do NOT commit `docs/knowledge.md`.
EOF