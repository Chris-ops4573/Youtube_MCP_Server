from pathlib import Path

import pytest

from ytmcp.providers.fixture import FixtureProvider


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def provider(fixtures_dir: Path) -> FixtureProvider:
    return FixtureProvider(fixtures_dir)