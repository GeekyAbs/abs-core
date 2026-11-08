# Portfolio Chatbot Backend — Plan

## Goal
Build a Python backend that powers a chatbot about Abesh Chakraborty (AI/ML engineer).
Dockerized, deployed on a VPS. Frontend integration comes later.

## Stack
- Python, managed with `uv`
- FastAPI for HTTP API
- LangGraph for the response loop (state graph, checkpointing)
- OpenRouter free models (chat + embeddings) — model IDs configurable via env
- Vector store: SQLite + sqlite-vec (small corpus, ~2-3 pages); FTS5 for keyword
- Hybrid retrieval: BM25 (FTS5) + vector, fused with RRF
- NeMo Guardrails (Colang) for input/output safety
- Personality: Marvel's Vision — philosophical, measured, not casual

## Architecture (LangGraph)
Nodes:
1. `guardrails_in` (NeMo input rail) — blocks jailbreaks, prompt injection, off-topic abuse
2. `retrieve` — embed query, top-k from sqlite-vec + FTS5, RRF fuse
3. `generate` — LLM with system prompt (Vision persona) + retrieved context
4. `guardrails_out` (NeMo output rail) — no PII leakage, no fabricated facts, tone check
5. Conditional: if retrieval empty / low confidence → graceful "I don't have that" node

Edges: START -> guardrails_in -> (blocked? END) else retrieve -> generate -> guardrails_out -> END
Checkpointing: MemorySaver (in-memory) for dev; SQLite checkpointer for prod sessions.

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

## Guardrails (Colang)
Files under `guardrails/`:
- `config.yml` — models, rails
- `main.co` — flows: jailbreak, off-topic, PII, hallucination guard
- Input rails: self-check input, jailbreak detection
- Output rails: self-check output (factuality against retrieved context), no secrets
- Allowed topics: Abesh, his work, skills, projects, contact, career. Decline politics, medical, financial advice, other people's private info, exploit/code-execution requests.

## System prompt (Vision persona)
- Address user respectfully; measured, philosophical, slightly formal
- Speak in first person about Abesh's experience/projects when asked
- Never fabricate; if unknown, say so plainly and offer contact
- Keep answers concise; cite sources loosely ("from his portfolio")
- No slang, no emojis, no excessive hedging

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
      ingest.py, retriever.py, chunking.py
    guardrails/
      config.yml, *.co
    db/
      sqlite.py, models.py
  scripts/
    ingest.py
  tests/
  Dockerfile
  docker-compose.yml
  docs/
    workflow.png

## Docker
- Multi-stage? Single stage python:3.12-slim, uv install, run uvicorn
- Volume for sqlite db + checkpoints
- docker-compose with env file

## Env vars
OPENROUTER_API_KEY, OPENROUTER_CHAT_MODEL, OPENROUTER_EMBED_MODEL,
CORS_ORIGINS, DB_PATH, CHECKPOINT_DB_PATH, RATE_LIMIT

## Verification
- uv sync
- uv run pytest
- uv run python -m app.graph.graph (prints mermaid + saves png)
- docker build + docker run + curl /health + /chat

## Open questions for user
1. Which OpenRouter free model(s) preferred? (default: google/gemini-2.0-flash-exp:free or meta-llama/llama-3.3-70b-instruct:free)
2. Persist chat history across restarts? (SQLite checkpointer) — yes recommended
3. Ingest resume PDF text? (need pdftotext or pypdf) — yes
4. Expose sources in API response? — yes, useful for frontend

## Next steps (after approval)
1. Scaffold with uv init, pyproject, .env.example
2. Implement config, db, rag ingest/retriever
3. Implement guardrails colang
4. Implement langgraph nodes + graph + mermaid export
5. FastAPI app + tests
6. Dockerfile + compose
7. Run & verify

---
Reply "go" to start scaffolding, or adjust.