#!/bin/sh
# Build the knowledge base on first boot, then hand off to the server.
set -eu

cd /app

DB="${DB_PATH:-./data/portfolio.db}"
if [ "${AUTO_INGEST:-1}" = "1" ] && [ ! -s "$DB" ]; then
    echo "entrypoint: knowledge base missing, ingesting into $DB"
    if ! .venv/bin/python scripts/ingest.py; then
        echo "entrypoint: ingest failed; /ready will report degraded" >&2
    fi
fi

exec "$@"
