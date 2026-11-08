# Portfolio Chatbot Backend — Plan

> **Implemented as of v0.2.0**, with two deliberate changes from this original
> plan: the bot is stateless (no checkpointer, no conversation memory), and NeMo
> Guardrails was replaced by deterministic checks in `app/safety.py`. See
> `README.md` for the shipped behaviour.

## Goal
Build a Python backend that powers a chatbot about Abesh Chakraborty (AI/ML engineer).
Dockerized, deployed on a VPS. Frontend integration comes later.

## Stack
- Python, managed with `uv`
- FastAPI for HTTP API
- LangGraph for the response loop (state graph)
- OpenRouter free models (chat + embeddings) — model IDs configurable via env
- Vector store: SQLite + sqlite-vec (small corpus, ~2-3 pages); FTS5 for keyword
- Hybrid retrieval: BM25 (FTS5) + vector, fused with RRF
- Deterministic input/output checks (`app/safety.py`) for injection and secret
  leakage — no LLM-based guardrail stack
- Personality: Marvel's Vision — philosophical, measured, not casual

## Architecture (LangGraph)
Nodes:
1. `check_input` — blocks jailbreaks and prompt injection
2. `retrieve` — embed query, top-k from sqlite-vec + FTS5, RRF fuse, similarity cutoff
3. `generate` — LLM with system prompt (Vision persona) + retrieved context
4. `check_output` — blocks key-shaped secret leakage

Edges: START -> check_input -> (blocked? END) else retrieve -> generate -> check_output -> END
No checkpointer: the API is stateless by design; an empty retrieval is handled
by the system prompt, which tells the model to say it does not know.

Workflow diagram exported via `graph.get_graph().draw_mermaid_png()` → `docs/workflow.png`.

## Data / Knowledge base
Source corpus (ingested once, re-ingest on content change):
- frontend/pages/Home.tsx content (experience, education, projects)
- frontend/components/Skills.tsx (skill groups)
- frontend/lib/site.ts (contact, availability)
- frontend/content/posts/*.md (blog posts)
- README / resume PDF text

Pipeline: markdown/text → chunk (RecursiveCharacterTextSplitter) → embed (OpenRouter embeddings) → sqlite-vec.
Store metadata: source, section, chunk_id.

## API (FastAPI)
- POST /chat {session_id, message} → {reply, sources?}
- GET /health
- CORS allowlist for portfolio origin (env)
- Rate limiting (slowapi) per IP
- Streaming optional via SSE later

## Safety

`app/safety.py` (superseded the Colang design):
- Input: NFKC-normalised regexes for instruction override, prompt extraction,
  jailbreak/DAN phrasing, and guardrail bypass attempts.
- Output: key-shaped strings, `OPENROUTER_API_KEY`, private-key blocks.
- The system prompt is static and contains no secrets, and the model only sees
  retrieved portfolio chunks.
- Allowed topics: Abesh, his work, skills, projects, contact, career.
  Politics, medical, financial advice, other people's private info, and
  code-execution requests are declined by the prompt.

## System prompt (Vision persona)
- Voice: measured, philosophical, precise, slightly formal; warmth implied, never performed
- Speaks of Abesh in the third person; never claims to be him
- Never fabricates; if unknown, says so plainly and offers contact
- Keeps answers to two to five sentences, in prose
- No slang, emoji, exclamation marks, or excessive hedging
- Reflects when it illuminates the work, never in place of the answer

## Project layout
backend/
  pyproject.toml (uv)
  .env.example
  app/
    main.py (FastAPI)
    config.py
    graph/
      state.py, nodes.py, graph.py, prompts.py
    rag/
      ingest.py, retriever.py, chunking.py, embeddings.py
    safety.py
    db/
      sqlite.py
  scripts/
    ingest.py, entrypoint.sh
  tests/
  Dockerfile
  docker-compose.yml
  docs/
    workflow.png

## Docker
- Multi-stage? Single stage python:3.12-slim, uv install, run uvicorn
- Volume for sqlite db
- docker-compose with env file

## Env vars
OPENROUTER_API_KEY, CHAT_MODEL, EMBED_MODEL, CORS_ORIGINS, DB_PATH,
RATE_LIMIT, MIN_SIMILARITY, TOP_K, MAX_MESSAGE_CHARS, MAX_TOKENS,
LLM_TIMEOUT, EMBED_TIMEOUT, KB_PATHS, LOG_LEVEL

## Verification
- uv sync
- uv run pytest
- uv run python -m app.graph.graph (prints the mermaid graph)
- docker build + docker run + curl /health, /ready, /chat

## Open questions for user
1. Which OpenRouter free model(s) preferred? (default: google/gemini-2.0-flash-exp:free or meta-llama/llama-3.3-70b-instruct:free)
2. Persist chat history across restarts? — no: the bot is intentionally stateless.
3. Ingest resume PDF text? (need pdftotext or pypdf) — yes
4. Expose sources in API response? — yes, useful for frontend

## Next steps (after approval)
1. Scaffold with uv init, pyproject, .env.example
2. Implement config, db, rag ingest/retriever
3. Implement deterministic input/output safety checks
4. Implement langgraph nodes + graph + mermaid export
5. FastAPI app + tests
6. Dockerfile + compose
7. Run & verify

---
Reply "go" to start scaffolding, or adjust.