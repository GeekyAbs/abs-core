from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import settings
from app.graph.graph import graph

app = FastAPI(title="Portfolio Chatbot", version="0.1.0")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.rate_limit)
def chat(req: ChatRequest, request: Request):
    state = {
        "session_id": req.session_id,
        "user_input": req.message,
        "retrieved": [],
        "reply": "",
        "blocked": False,
        "block_reason": "",
    }
    out = graph.invoke(state)
    sources = list({c.get("source", "") for c in out.get("retrieved", [])})
    return ChatResponse(reply=out.get("reply", ""), sources=sources)