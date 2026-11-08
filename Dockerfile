FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir uv

# Dependencies first so code edits do not invalidate the layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=10001:10001 . .

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data \
    && chown -R 10001:10001 /app/data \
    && chmod +x /app/scripts/entrypoint.sh

USER app

EXPOSE 8000

# /ready fails until the API key is present and the corpus is ingested.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=4)"]

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
# FORWARDED_ALLOW_IPS is read by uvicorn (default 127.0.0.1).
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
