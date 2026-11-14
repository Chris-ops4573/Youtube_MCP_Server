from pathlib import Path

import pytest

from ytmcp.providers.fixture import FixtureProvider

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def provider():
    return FixtureProvider(FIXTURES)


def test_get_videos_returns_known_ids(provider):
    videos = provider.get_videos(["aaaaaaaaaaa", "zzzzzzzzzzz"])
    assert [v.id for v in videos] == ["aaaaaaaaaaa"]


def test_search_matches_title_terms(provider):
    results = provider.search_videos("rust")
    assert {v.id for v in results} == {"aaaaaaaaaaa", "bbbbbbbbbbb"}


def test_get_channels_hidden_subscribers(provider):
    (channel,) = provider.get_channels(["UC2"])
    assert channel.subscriber_count is None