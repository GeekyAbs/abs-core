# Docs

Place your personal portfolio knowledge in `docs/knowledge.md` (gitignored) —
experience, projects, skills, contact, etc. Then run:

```bash
uv run python scripts/ingest.py
```

This builds `data/portfolio.db`. Docker Compose mounts both `./data` (via a
named volume) and `./docs` (read-only), so the database persists and the image
never contains personal content.

A template is provided as `docs/knowledge.md.example`. Copy it to
`docs/knowledge.md` and fill in your info. Do **not** commit `docs/knowledge.md`.

To ingest additional markdown, set `KB_PATHS`:

```bash
KB_PATHS='docs/knowledge.md,../frontend/content/posts/*.md' uv run python scripts/ingest.py
```
