# Portfolio Chatbot Backend

FastAPI + LangGraph backend for the assistant on [abesh.site](https://abesh.site).
Hybrid retrieval over a private corpus, deterministic safety checks, and no
conversation memory.

## Pipeline

```
POST /chat
  -> check_input    prompt-injection check
  -> retrieve       sqlite-vec (cosine) + FTS5 BM25, fused with RRF
  -> generate       OpenRouter chat model, grounded in context
  -> check_output   secret-leak check
```

- **Storage:** SQLite + `sqlite-vec`; ingestion is atomic and records the
  embedding dimension.
- **Safety:** NFKC-normalised regex checks. The prompt is static and contains
  no credentials.
- **Stateless:** `session_id` exists only for log correlation.

## Local development

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env                              # set OPENROUTER_API_KEY
cp docs/knowledge.md.example docs/knowledge.md    # fill in your details
uv run python scripts/ingest.py
uv run uvicorn app.main:app --reload
```

`GET /health` is liveness. `GET /ready` returns 503 until the API key is set
and the corpus exists.

## Configuration

Environment variables, documented in `.env.example`. The important ones:

- `OPENROUTER_API_KEY` — required; chat and embeddings go through OpenRouter.
- `DB_PATH` — knowledge base path (default `./data/portfolio.db`).
- `CORS_ORIGINS` — comma-separated allowlist for the frontend origin.
- `RATE_LIMIT` — per-IP limit (default `20/minute`).
- `KB_PATHS` — files or globs ingested into the corpus.
- `MIN_SIMILARITY`, `TOP_K`, `MAX_TOKENS` — retrieval and generation bounds.

## Knowledge base

`docs/knowledge.md` is gitignored and must never be committed. Ingestion builds
into `DB_PATH.building` and swaps it in with `os.replace`, so a failed embedding
call leaves the previous index intact. Re-ingest after changing the content or
the embedding model.

## Docker

```bash
docker compose up --build
```

The entrypoint ingests on first boot if the database is missing. Compose
publishes the service on `127.0.0.1:8000` and keeps the database in a named
volume.

## Deploy

Terminate TLS with Caddy or Cloudflare in front of the container. Set
`CORS_ORIGINS` to the site origin and `FORWARDED_ALLOW_IPS` to the trusted
proxy (loopback by default; Cloudflare's ranges if proxied). Keep port 8000
closed to the public. See `deploy/Caddyfile.example`.

## Tests

```bash
uv run pytest
uv run ruff check app scripts tests
```

The suite stubs embeddings and the chat model; it needs no network or API key.
