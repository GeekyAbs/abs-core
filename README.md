# Portfolio Chatbot Backend

FastAPI backend powering a chatbot about Abesh Chakraborty's portfolio. RAG over personal knowledge, LangGraph response loop, NeMo Guardrails, OpenRouter models.

## Run locally

    uv sync
    cp .env.example .env   # fill OPENROUTER_API_KEY
    cp docs/knowledge.md.example docs/knowledge.md  # fill your info
    uv run python scripts/ingest.py
    uv run uvicorn app.main:app --reload

## Docker

    docker compose up --build

## API

    POST /chat  { "session_id": "...", "message": "..." }
    GET  /health

## Notes

- `docs/knowledge.md` is gitignored (personal info). Never commit.
- Data persists in `./data`.
EOF