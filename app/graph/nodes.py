import logging

from langchain_openai import ChatOpenAI

from app.config import settings
from app.graph.prompts import SYSTEM_PROMPT
from app.graph.state import ChatState
from app.rag.retriever import retrieve
from app.safety import check_input, check_output
from app.voice import REFUSAL, SECRET_REFUSAL

log = logging.getLogger(__name__)


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0.3,
        timeout=settings.llm_timeout,
        max_retries=2,
        max_tokens=settings.max_tokens,
        default_headers={
            "HTTP-Referer": settings.app_url,
            "X-Title": settings.app_title,
        },
    )


def check_input_node(state: ChatState) -> ChatState:
    verdict = check_input(state["user_input"])
    state["blocked"] = not verdict.allowed
    if verdict.allowed:
        state["block_reason"] = ""
    else:
        state["block_reason"] = verdict.reason
        state["reply"] = REFUSAL
    return state


def retrieve_node(state: ChatState) -> ChatState:
    if state.get("blocked"):
        return state
    state["retrieved"] = retrieve(state["user_input"])
    return state


def generate_node(state: ChatState) -> ChatState:
    if state.get("blocked"):
        return state

    context = "\n\n".join(chunk["content"] for chunk in state.get("retrieved", []))
    messages = [
        ("system", SYSTEM_PROMPT),
        ("system", f"Context:\n{context}" if context else "Context: (none)"),
        ("human", state["user_input"]),
    ]
    response = _llm().invoke(messages)
    state["reply"] = str(response.content or "")

    usage = getattr(response, "usage_metadata", None)
    if usage:
        log.info(
            "llm usage: prompt=%s completion=%s total=%s",
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("total_tokens"),
        )
    return state


def check_output_node(state: ChatState) -> ChatState:
    if state.get("blocked"):
        return state

    verdict = check_output(state["reply"])
    if not verdict.allowed:
        state["blocked"] = True
        state["block_reason"] = verdict.reason
        state["reply"] = SECRET_REFUSAL
    return state
