# Portfolio Chatbot Backend

FastAPI backend for the chatbot on [abesh.site](https://abesh.site). Hybrid RAG
over a small personal corpus, a LangGraph response loop, and deterministic
input/output safety checks.

The bot is **stateless**. It does not store conversations or remember previous
turns; `session_id` is accepted only for request correlation in logs.

## Pipeline

```
POST /chat
  -> check_input      deterministic prompt-injection check
  -> retrieve         sqlite-vec (cosine) + FTS5 BM25, fused with RRF
  -> generate         OpenRouter chat model, grounded in retrieved context
  -> check_output     secret-leak check
  -> reply
```

- **Vector store:** SQLite + `sqlite-vec`, cosine distance, dimension recorded
  at ingest time.
- **Keyword search:** FTS5, ranked by BM25. User input is tokenised and quoted
  before it reaches `MATCH`, so punctuation cannot raise an FTS syntax error.
- **Fusion:** reciprocal rank fusion (`k = 60`).
- **Relevance cutoff:** vector hits below `MIN_SIMILARITY` are dropped. When
  nothing is retrieved the prompt tells the model to say it does not know and
  offer the contact address.
- **Safety:** regex-based checks (NFKC-normalised) rather than NeMo Guardrails.
  Input rails block jailbreak/prompt-extraction patterns; output rails block
  key-shaped strings. The prompt is static and contains no credentials.

## Local development

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env                 # add OPENROUTER_API_KEY
cp docs/knowledge.md.example docs/knowledge.md
# ... fill in docs/knowledge.md ...
uv run python scripts/ingest.py
uv run uvicorn app.main:app --reload
```

```bash
curl -s localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"session_id":"local","message":"What has Abesh built?"}'
# {"reply":"...","sources":["docs/knowledge.md"]}
```

`GET /health` is liveness. `GET /ready` returns 503 until the API key is set
and the corpus is ingested.

## Configuration

All settings come from environment variables or `.env` (see `.env.example`).

| Variable | Default | Notes |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | – | Required. Chat and embeddings both go through OpenRouter. |
| `CHAT_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | Any OpenRouter chat model. |
| `EMBED_MODEL` | `openai/text-embedding-3-small` | Embeddings are **billed**, not free-tier. A few pages cost pennies. |
| `DB_PATH` | `./data/portfolio.db` | Knowledge base. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowlist. Set the production origin. |
| `RATE_LIMIT` | `20/minute` | Per client IP. |
| `MIN_SIMILARITY` | `0.35` | Cosine similarity floor for vector hits. |
| `TOP_K` | `5` | Chunks passed to the model. |
| `MAX_MESSAGE_CHARS` | `2000` | Request validation limit. |
| `MAX_TOKENS` | `400` | Generation cap. |
| `LLM_TIMEOUT` / `EMBED_TIMEOUT` | `30` / `20` | Seconds, with retries on the client. |
| `KB_PATHS` | `docs/knowledge.md,docs/knowledge.txt` | Comma-separated files or globs, relative to `backend/`. |
| `LOG_LEVEL` | `INFO` | |

## Knowledge base

`docs/knowledge.md` is gitignored and must never be committed. To include blog
posts or other generated markdown, point `KB_PATHS` at them:

```bash
KB_PATHS='docs/knowledge.md,../frontend/content/posts/*.md' uv run python scripts/ingest.py
```

Ingestion builds into `DB_PATH + ".building"` and atomically replaces the live
database only after every chunk is embedded. A provider failure therefore
leaves the existing corpus untouched. Re-ingest whenever the content or the
embedding model changes; changing the model's dimension rebuilds the schema
automatically.

`TSX` sources are deliberately not parsed. Keep the canonical facts in
`docs/knowledge.md` (or generate that file from the frontend at build time).

## Docker

```bash
cp .env.example .env                 # add OPENROUTER_API_KEY
docker compose up --build
```

On first boot the entrypoint runs `scripts/ingest.py` if the database is
missing. `docs/` is mounted read-only so the image itself never contains
personal content; the database lives in the `chatbot-data` named volume.

```bash
docker compose run --rm chatbot .venv/bin/python scripts/ingest.py   # re-ingest
docker compose exec chatbot .venv/bin/python -c \
  "import sqlite3; c=sqlite3.connect('/app/data/portfolio.db'); print(c.execute('select count(*) from chunks').fetchone())"
```

The container runs as UID 10001, binds to `127.0.0.1:8000`, and its healthcheck
calls `/ready`.

## Deploying on a VPS (frontend stays on Cloudflare Pages)

The browser calls the API over HTTPS, so the origin needs TLS. Two workable
setups:

**A. Cloudflare in front of the VPS (recommended).** Proxied DNS record
(`api.abesh.site`, orange cloud), origin on `127.0.0.1:8000`. Then:

- Set `CORS_ORIGINS=https://abesh.site,https://www.abesh.site`.
- Set `FORWARDED_ALLOW_IPS` to Cloudflare's ranges (or terminate TLS with a
  Cloudflare Tunnel and keep the port closed). Otherwise every request appears
  to come from a Cloudflare edge IP and the whole site shares one 20/min
  bucket.
- Block direct access to port 8000 with the firewall.

**B. Caddy on the VPS.** Use `deploy/Caddyfile.example`
(`api.abesh.site { reverse_proxy 127.0.0.1:8000 }`). Caddy connects from
loopback, so the container's default `FORWARDED_ALLOW_IPS=127.0.0.1` resolves
the real client IP from `X-Forwarded-For`.

Either way, add `https://abesh.site` to `CORS_ORIGINS` and never expose the
OpenRouter key to the browser. A third option is to proxy `/api/chat` through
the existing Cloudflare Worker: same-origin requests, edge rate limiting, and no
CORS at all.

## Tests

```bash
uv run pytest
uv run ruff check app scripts tests
```

The suite stubs embeddings and the chat model; it needs no API key and makes no
network calls. It covers the FTS syntax regressions, atomic ingestion,
dimension changes, request validation, readiness, CORS, and the full graph
including the blocked path.

## Notes

- Conversation memory is intentionally absent. Every request is independent.
- `scripts/ingest.py` resolves paths relative to `backend/`, so it works from
  any working directory.
- All visitor-facing copy lives in `app/voice.py`; the persona prompt lives in
  `app/graph/prompts.py`. Logs, `/ready` issues, and CLI errors stay plain so
  operators can diagnose them.
