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
    (channel,) = provider.get_channels(["UC2222222222222222222222"])
    assert channel.subscriber_count is None

def test_category_names_come_from_the_optional_file(provider):
    assert provider.category_names() == {"26": "Howto & Style", "27": "Education"}


def test_without_a_categories_file_there_are_no_names(tmp_path):
    import shutil

    for name in ("videos.json", "channels.json"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    assert FixtureProvider(tmp_path).category_names() == {}


def test_a_provider_that_cannot_look_names_up_returns_none():
    from fake_playlists import ListProvider

    assert ListProvider([]).category_names() == {}  # the default on the base class
