"""FastAPI entrypoint.

The bot is intentionally stateless: there is no conversation memory, so
``session_id`` is accepted only so a future frontend can correlate requests in
logs. It is not used by the graph.
"""

import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.db.sqlite import connect
from app.graph.graph import graph
from app.rag.retriever import RetrievalUnavailable
from app.voice import (
    KNOWLEDGE_UNAVAILABLE,
    NOT_CONFIGURED,
    RATE_LIMITED,
    UNAVAILABLE,
)

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def readiness_issues() -> list[str]:
    issues: list[str] = []
    if not settings.is_llm_configured:
        issues.append("OPENROUTER_API_KEY is not set")

    path = Path(settings.db_path)
    if not path.exists():
        issues.append(f"knowledge base missing at {path}; run scripts/ingest.py")
        return issues

    try:
        conn = connect(path)
        try:
            chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error as exc:
        issues.append(f"knowledge base unreadable: {exc}")
        return issues

    if chunks == 0:
        issues.append(f"knowledge base at {path} is empty; run scripts/ingest.py")
    return issues


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "starting: model=%s embed=%s db=%s",
        settings.chat_model,
        settings.embed_model,
        settings.db_path,
    )
    for issue in readiness_issues():
        log.warning("not ready: %s", issue)
    yield
    log.info("shutting down")


app = FastAPI(title="Portfolio Chatbot", version="0.2.0", lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def rate_limit_exceeded(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": RATE_LIMITED})


app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("cf-ray") or uuid4().hex[:12]
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    log.info(
        "%s %s -> %s %.0fms rid=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


class ChatRequest(BaseModel):
    session_id: str = Field(default="", max_length=128)
    message: str = Field(min_length=1, max_length=settings.max_message_chars)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = Field(default_factory=list)


@app.get("/health")
def health():
    """Liveness: the process is up. Readiness lives at /ready."""
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response):
    issues = readiness_issues()
    if issues:
        response.status_code = 503
        return {"status": "degraded", "issues": issues}
    return {"status": "ok", "issues": []}


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.rate_limit)
def chat(req: ChatRequest, request: Request):
    if not settings.is_llm_configured:
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED)

    state = {
        "session_id": req.session_id,
        "user_input": req.message,
        "retrieved": [],
        "reply": "",
        "blocked": False,
        "block_reason": "",
    }

    try:
        out = graph.invoke(state)
    except RetrievalUnavailable as exc:
        log.warning("knowledge base unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=KNOWLEDGE_UNAVAILABLE) from exc
    except Exception as exc:
        log.exception("chat request failed")
        raise HTTPException(status_code=502, detail=UNAVAILABLE) from exc

    sources = sorted({chunk["source"] for chunk in out.get("retrieved", []) if chunk.get("source")})
    return ChatResponse(reply=out.get("reply", ""), sources=sources)
