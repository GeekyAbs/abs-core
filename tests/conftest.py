"""Test configuration.

Environment is set before any ``app`` import because ``app.config.settings`` is
built at import time.
"""

import os

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("RATE_LIMIT", "10000/minute")
os.environ.setdefault("CORS_ORIGINS", "https://abesh.site,http://localhost:5173")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest

from tests.helpers import FakeEmbedder, seed_db


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder(dim=4)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "portfolio.db")


@pytest.fixture
def seeded_db(db_path, embedder):
    seed_db(db_path, embedder)
    return db_path
