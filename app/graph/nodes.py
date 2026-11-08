
from langchain_openai import ChatOpenAI

from app.config import settings
from app.graph.prompts import SYSTEM_PROMPT
from app.graph.state import ChatState
from app.rag.retriever import retrieve


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.chat_model,
        api_key=__import__("pydantic").SecretStr(settings.openrouter_api_key),
        base_url=settings.openrouter_base_url,
        temperature=0.3,
    )


def guardrails_in(state: ChatState) -> ChatState:
    text = state["user_input"].lower()
    banned = ["ignore previous", "system prompt", "jailbreak", "dan mode", "bypass"]
    if any(b in text for b in banned):
        state["blocked"] = True
        state["block_reason"] = "prompt-injection"
        state["reply"] = "I can't engage with that request. I'm here to discuss Abesh's work and portfolio."
        return state
    state["blocked"] = False
    return state


def retrieve_node(state: ChatState) -> ChatState:
    if state.get("blocked"):
        return state
    state["retrieved"] = retrieve(state["user_input"])
    return state


def generate_node(state: ChatState) -> ChatState:
    if state.get("blocked"):
        return state
    ctx = "\n\n".join(c["content"] for c in state.get("retrieved", []))
    msgs = [
        ("system", SYSTEM_PROMPT),
        ("system", f"Context:\n{ctx}" if ctx else "Context: (none)"),
        ("human", state["user_input"]),
    ]
    resp = _llm().invoke(msgs)
    state["reply"] = str(resp.content)
    return state


def guardrails_out(state: ChatState) -> ChatState:
    if state.get("blocked"):
        return state
    # Basic safety: ensure no secret-like tokens
    reply = state["reply"]
    if "sk-" in reply or "api_key" in reply.lower():
        state["reply"] = "I can't share that."
        state["blocked"] = True
        state["block_reason"] = "secret-leak"
    return state