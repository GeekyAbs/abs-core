"""Embedding client shared by ingestion and retrieval."""

from langchain_openai import OpenAIEmbeddings

from app.config import settings


def build_embedder() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embed_model,
        api_key=settings.openrouter_api_key.get_secret_value(),
        base_url=settings.openrouter_base_url,
        # Send plain strings rather than locally tokenised input: OpenRouter
        # proxies several providers and not all accept token arrays.
        check_embedding_ctx_length=False,
        timeout=settings.embed_timeout,
        max_retries=2,
        chunk_size=64,
    )
