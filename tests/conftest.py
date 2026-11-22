import contextlib
import sqlite3
from pathlib import Path

import pytest

from ytmcp import cache as cache_module
from ytmcp.providers.fixture import FixtureProvider


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def provider(fixtures_dir: Path) -> FixtureProvider:
    return FixtureProvider(fixtures_dir)


@pytest.fixture(autouse=True)
def close_caches(monkeypatch):
    """Close every Cache a test opens, so no database is left unclosed."""
    opened = []
    original = cache_module.Cache.__init__

    def tracking_init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        opened.append(self)

    monkeypatch.setattr(cache_module.Cache, "__init__", tracking_init)
    yield
    for cache in opened:
        with contextlib.suppress(sqlite3.Error):  # a test may have closed it already
            cache.close()
