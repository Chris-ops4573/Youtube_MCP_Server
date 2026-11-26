"""FR-3: taste profile, recommendations, the tool, and the tool over the real MCP protocol."""

import asyncio
import json

import pytest
from fake_playlists import FakeAccount
from mcp import Client

from ytmcp.database import Database
from ytmcp.errors import (
    AccountUnavailableError,
    AuthRequiredError,
    NotEnoughHistoryError,
    QuotaExceededError,
)
from ytmcp.models import LikedVideo, Subscription, Video
from ytmcp.proposals import ProposalStore
from ytmcp.providers.base import VideoProvider
from ytmcp.server import create_server
from ytmcp.services.recommendations import (
    LIKES_CAP,
    PLAYLISTS_CAP,
    SEARCH_SIZE,
    SUBSCRIPTIONS_CAP,
    estimate_cost,
    recommend_videos,
)
from ytmcp.similarity import (
    DEFAULT_TASTE_WEIGHTS,
    TasteProfile,
    build_taste_profile,
    rank_for_profile,
    reason_for,
)
from ytmcp.tools import recommend_videos_tool


def vid(vid_id, title="A video", tags=(), category=None, channel="UCnone", channel_title="Chan", seconds=600):
    return Video(
        id=vid_id, title=title, description="", channel_id=channel, channel_title=channel_title,
        tags=list(tags), category_id=category, duration_seconds=seconds,
    )


class TasteProvider(VideoProvider):
    """Records what it is asked. get_videos answers from `details`, search from `candidates`."""

    def __init__(self, details=(), candidates=(), budget_error=None):
        self.details = {v.id: v for v in details}
        self.candidates = list(candidates)
        self.budget_error = budget_error
        self.events: list[tuple] = []

    def ensure_budget(self, units):
        self.events.append(("budget", units))
        if self.budget_error:
            raise self.budget_error

    def get_videos(self, video_ids):
        self.events.append(("get_videos", list(video_ids)))
        return [self.details[i] for i in video_ids if i in self.details]

    def search_videos(self, query, max_results=25):
        self.events.append(("search", query, max_results))
        return list(self.candidates)

    def get_channels(self, channel_ids):
        return []

    def get_channel_by_handle(self, handle):
        return None

    def get_recent_uploads(self, channel_id, max_results=10):
        return []

    def kinds(self):
        return [event[0] for event in self.events]


# --- build_taste_profile ---------------------------------------------------------------------------------------


RUST_LIKES = [
    vid("a", "Rust ownership", ["rust"], "27", "UC1"),
    vid("b", "Rust lifetimes tutorial", ["rust"], "27", "UC1"),
    vid("c", "The Rust borrow checker", [], "28", "UC2"),
    vid("d", "Baking bread", [], None, "UC3"),
]


def test_the_profile_text_is_the_liked_titles_and_tags():
    profile = build_taste_profile(RUST_LIKES, [], [])
    assert "Rust ownership" in profile.text and "Baking bread" in profile.text and "rust" in profile.text


def test_top_terms_exact_for_a_small_case():
    liked = [vid("a", "Rust ownership"), vid("b", "Rust lifetimes tutorial"), vid("c", "The Rust borrow checker")]
    profile = build_taste_profile(liked, [], [], term_count=3)
    assert profile.top_terms == ["rust", "borrow", "checker"]  # rust x3, then ties in alphabetical order


@pytest.mark.parametrize("count, expected", [(1, ["rust"]), (2, ["rust", "borrow"]), (0, [])])
def test_term_count_limits_the_terms(count, expected):
    liked = [vid("a", "Rust ownership"), vid("b", "The Rust borrow checker")]
    assert build_taste_profile(liked, [], [], term_count=count).top_terms == expected


def test_stop_words_short_words_digits_and_symbols_are_not_terms():
    liked = [vid("a", "The and with 2026 AI go #1 !!! guide for you")]
    assert build_taste_profile(liked, [], []).top_terms == ["guide"]


def test_non_english_words_are_kept():
    assert "programação" in build_taste_profile([vid("a", "Programação em Rust")], [], []).top_terms


def test_subscription_titles_stand_in_when_there_are_no_likes():
    profile = build_taste_profile([], ["Fireship", "Rust Lab"], ["UCs1"])
    assert profile.text == "Fireship Rust Lab"
    assert profile.top_terms == ["fireship", "lab", "rust"]


def test_subscription_titles_are_ignored_when_there_are_likes():
    profile = build_taste_profile([vid("a", "Rust ownership")], ["Cooking channel"], [])
    assert "cooking" not in profile.top_terms and "Cooking" not in profile.text


def test_category_shares_are_a_share_of_all_likes():
    profile = build_taste_profile(RUST_LIKES, [], [])
    assert profile.category_share == {"27": 0.5, "28": 0.25}  # the like with no category still counts in the 4


def test_channels_are_the_liked_ones_plus_the_subscribed_ones():
    profile = build_taste_profile(RUST_LIKES, [], ["UCsub"])
    assert profile.channel_ids == frozenset({"UC1", "UC2", "UC3", "UCsub"})


def test_an_empty_history_gives_an_empty_profile():
    profile = build_taste_profile([], [], [])
    assert (profile.text, profile.top_terms, profile.category_share, profile.channel_ids) == ("", [], {}, frozenset())


def test_terms_shares_and_channels_do_not_depend_on_the_order_of_likes():
    first = build_taste_profile(RUST_LIKES, [], [])
    again = build_taste_profile(list(reversed(RUST_LIKES)), [], [])
    assert (first.top_terms, first.category_share, first.channel_ids) == (again.top_terms, again.category_share, again.channel_ids)


# --- reason_for ------------------------------------------------------------------------------------------------


PROFILE = TasteProfile(
    text="rust borrow checker", top_terms=["rust", "borrow"],
    category_share={"27": 0.5, "28": 0.19, "29": 0.20}, channel_ids=frozenset({"UC1"}),
)


def test_reason_one_a_channel_you_like():
    reason = reason_for(PROFILE, vid("x", "Anything", channel="UC1", channel_title="Rust Lab"))
    assert reason == "From a channel you like or subscribe to: Rust Lab"


def test_reason_two_shared_interest_words():
    assert reason_for(PROFILE, vid("x", "Rust and the borrow checker")) == "Matches your interests: rust, borrow"
    assert reason_for(PROFILE, vid("x", "Learning Rust")) == "Matches your interests: rust"


def test_interest_words_must_be_whole_words():
    assert reason_for(PROFILE, vid("x", "Trust issues")) == "Similar to videos you liked"  # "rust" is inside "trust"


def test_reason_three_a_category_you_like_often():
    assert reason_for(PROFILE, vid("x", "Something else", category="27")) == "In a category you like often (50% of your likes)"


def test_the_category_threshold_is_twenty_percent():
    assert reason_for(PROFILE, vid("x", "Other", category="29")).startswith("In a category you like often (20%")
    assert reason_for(PROFILE, vid("x", "Other", category="28")) == "Similar to videos you liked"  # 19%


def test_reason_four_is_the_fallback():
    assert reason_for(PROFILE, vid("x", "Other", category="99")) == "Similar to videos you liked"
    assert reason_for(PROFILE, vid("x", "Other")) == "Similar to videos you liked"


def test_the_first_reason_that_applies_wins():
    both = vid("x", "Rust borrow", category="27", channel="UC1", channel_title="Rust Lab")
    assert reason_for(PROFILE, both).startswith("From a channel")
    assert reason_for(PROFILE, vid("y", "Rust borrow", category="27")).startswith("Matches your interests")


# --- rank_for_profile ---------------------------------------------------------------------------------------------


def test_default_taste_weights_sum_to_one():
    assert sum(DEFAULT_TASTE_WEIGHTS.values()) == pytest.approx(1)


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        rank_for_profile(PROFILE, [vid("a")], weights={"text": 0.5, "category": 0.2, "channel": 0.2})


def test_the_best_match_ranks_first():
    candidates = [
        vid("far", "Baking sourdough bread at home", category="26", channel="UC9"),
        vid("near", "Rust borrow checker explained", category="27", channel="UC1"),
    ]
    ranked = rank_for_profile(PROFILE, candidates)
    assert [r.video.id for r in ranked] == ["near", "far"]
    assert ranked[0].score > ranked[1].score


def test_the_score_is_the_weighted_breakdown():
    (item,) = rank_for_profile(PROFILE, [vid("a", "Rust borrow", category="27", channel="UC1")])
    b = item.breakdown
    assert (b.category, b.channel) == (0.5, 1.0)
    expected = sum(w * getattr(b, name) for name, w in DEFAULT_TASTE_WEIGHTS.items())
    assert item.score == pytest.approx(expected)
    assert 0 <= b.text <= 1


def test_duplicates_are_dropped_and_ties_break_by_id():
    same = [vid("b", "Same title"), vid("a", "Same title"), vid("b", "Same title")]
    assert [r.video.id for r in rank_for_profile(PROFILE, same)] == ["a", "b"]


def test_top_n_limits_and_empty_input_is_fine():
    many = [vid(f"id{n}", "Rust borrow") for n in range(5)]
    assert len(rank_for_profile(PROFILE, many, top_n=2)) == 2
    assert rank_for_profile(PROFILE, []) == []


def test_results_are_deterministic():
    candidates = [vid(f"id{n}", f"Rust topic {n}") for n in range(6)]
    assert rank_for_profile(PROFILE, candidates) == rank_for_profile(PROFILE, list(reversed(candidates)))


def test_a_profile_with_no_words_does_not_crash():
    empty = TasteProfile("", [], {}, frozenset())
    assert rank_for_profile(empty, [vid("a", "Rust")])[0].breakdown.text == 0.0


# --- the service -----------------------------------------------------------------------------------------------------


LIKED = [LikedVideo("a", "2026-11-10T00:00:00Z"), LikedVideo("b", "2026-11-09T00:00:00Z")]
DETAILS = [vid("a", "Rust ownership", ["rust"], "27", "UC1", "Rust Lab"), vid("b", "Rust lifetimes", ["rust"], "27", "UC1", "Rust Lab")]
SUBS = [Subscription("UCsub", "Fireship", "2025-01-01T00:00:00Z")]


def setup(liked=LIKED, subs=SUBS, playlist_ids=("pl1",), details=DETAILS, candidates=(), **account_kwargs):
    account = FakeAccount(liked=liked, subscribed=subs, playlist_ids=playlist_ids, **account_kwargs)
    provider = TasteProvider(details=details, candidates=candidates)
    return provider, account


def test_the_cost_is_127_units():
    assert estimate_cost() == 127
    assert (LIKES_CAP, SUBSCRIPTIONS_CAP, PLAYLISTS_CAP, SEARCH_SIZE) == (250, 200, 10, 50)
    assert 1 + 5 + 4 + 1 + 10 + 5 + 100 + 1 == 127


def test_liked_saved_and_duplicate_videos_are_left_out():
    candidates = [
        vid("a", "Rust ownership"),  # already liked
        vid("pl1", "Rust in a playlist"),  # already in a playlist
        vid("new1", "Rust traits", channel="UC1"),
        vid("new1", "Rust traits", channel="UC1"),  # a duplicate
        vid("new2", "More rust"),
    ]
    provider, account = setup(candidates=candidates)
    result = recommend_videos(provider, account)
    assert sorted(r.video.id for r in result.results) == ["new1", "new2"]
    assert (result.likes, result.subscriptions, result.playlist_videos) == (2, 1, 1)


def test_a_liked_video_is_excluded_even_when_its_details_were_not_returned():
    provider, account = setup(liked=[*LIKED, LikedVideo("gone", "2026-11-01T00:00:00Z")], candidates=[vid("gone", "Rust deleted one"), vid("ok", "Rust fine")])
    assert [r.video.id for r in recommend_videos(provider, account).results] == ["ok"]


def test_the_search_uses_the_top_terms_and_asks_for_50():
    provider, account = setup(candidates=[vid("x", "Rust")])
    recommend_videos(provider, account)
    search = next(e for e in provider.events if e[0] == "search")
    assert search[1] == "rust lifetimes ownership"  # rust x4 (titles + tags), then ties alphabetically
    assert search[2] == 50


def test_the_liked_videos_details_are_fetched_with_all_their_ids():
    provider, account = setup(candidates=[vid("x", "Rust")])
    recommend_videos(provider, account)
    assert ("get_videos", ["a", "b"]) in provider.events


def test_the_caps_are_passed_exactly():
    provider, account = setup(candidates=[vid("x", "Rust")])
    recommend_videos(provider, account)
    assert ("liked", 250) in account.events
    assert ("subscriptions", 200) in account.events
    assert ("playlists", 10) in account.events


def test_the_budget_is_checked_first_and_nothing_else_happens_when_it_fails():
    provider, account = setup()
    provider.budget_error = QuotaExceededError("needs 127, 10 left")
    with pytest.raises(QuotaExceededError):
        recommend_videos(provider, account)
    assert provider.events == [("budget", 127)]
    assert account.events == []  # not a single call about the user's account


def test_without_an_account_nothing_is_called_at_all():
    provider = TasteProvider()
    with pytest.raises(AccountUnavailableError) as exc:
        recommend_videos(provider, None)
    assert exc.value.code == "ACCOUNT_NOT_AVAILABLE"
    assert provider.events == []


def test_no_likes_and_no_subscriptions_is_not_enough_history():
    provider, account = setup(liked=[], subs=[])
    with pytest.raises(NotEnoughHistoryError) as exc:
        recommend_videos(provider, account)
    assert exc.value.code == "NOT_ENOUGH_HISTORY"
    assert "playlists" not in [e[0] for e in account.events]  # does not spend units reading playlists
    assert "search" not in provider.kinds()


def test_likes_with_no_usable_words_cannot_be_searched():
    provider, account = setup(details=[vid("a", "The and of"), vid("b", "A B")], subs=[])
    with pytest.raises(NotEnoughHistoryError):
        recommend_videos(provider, account)
    assert "search" not in provider.kinds()


def test_subscriptions_alone_are_enough():
    provider, account = setup(liked=[], subs=[Subscription("UC1", "Rust Lab"), Subscription("UC2", "Rust News")], details=[], candidates=[vid("x", "Rust")])
    result = recommend_videos(provider, account)
    search = next(e for e in provider.events if e[0] == "search")
    assert search[1] == "rust lab news"
    assert result.low_confidence is True and result.likes == 0


def test_not_signed_in_passes_through_and_nothing_is_searched():
    provider, account = setup(read_error=AuthRequiredError("You are not signed in."))
    with pytest.raises(AuthRequiredError) as exc:
        recommend_videos(provider, account)
    assert exc.value.code == "AUTH_REQUIRED"
    assert "search" not in provider.kinds()


@pytest.mark.parametrize("likes, low", [(4, True), (5, False), (0, True)])
def test_low_confidence_needs_at_least_five_likes(likes, low):
    liked = [LikedVideo(f"l{n}", "2026-01-01T00:00:00Z") for n in range(likes)]
    details = [vid(f"l{n}", "Rust topic") for n in range(likes)]
    provider, account = setup(liked=liked, details=details, candidates=[vid("x", "Rust")])
    assert recommend_videos(provider, account).low_confidence is low


def test_top_n_is_respected_and_results_are_stable():
    candidates = [vid(f"c{n}", f"Rust topic {n}") for n in range(8)]
    provider, account = setup(candidates=candidates)
    first = recommend_videos(provider, account, top_n=3)
    again = recommend_videos(*setup(candidates=list(reversed(candidates))), top_n=3)
    assert len(first.results) == 3
    assert [r.video.id for r in first.results] == [r.video.id for r in again.results]


# --- the tool ----------------------------------------------------------------------------------------------------------


def test_tool_output_shape():
    candidates = [vid("new1", "Rust traits explained", category="27", channel="UC1", channel_title="Rust Lab", seconds=3870)]
    provider, account = setup(candidates=candidates)
    out = recommend_videos_tool(provider, account)
    (item,) = out["results"]
    assert item["rank"] == 1 and item["title"] == "Rust traits explained"
    assert item["channel"] == "Rust Lab" and item["duration"] == "1:04:30"
    assert item["url"] == "https://www.youtube.com/watch?v=new1"
    assert item["reason"].startswith("From a channel you like")
    assert set(item["score_breakdown"]) == {"text", "category", "channel"}
    assert 0 <= item["score"] <= 1 and item["score"] == round(item["score"], 3)
    assert out["based_on"] == {"likes": 2, "subscriptions": 1, "playlist_videos": 1}
    assert out["low_confidence"] is True


def test_the_tool_never_reveals_what_you_liked():
    provider, account = setup(candidates=[vid("new1", "Rust traits")])
    text = json.dumps(recommend_videos_tool(provider, account))
    assert "Rust ownership" not in text and "Rust lifetimes" not in text and "Fireship" not in text


@pytest.mark.parametrize("top_n", [0, -1, 51])
def test_top_n_out_of_range_makes_no_call(top_n):
    provider, account = setup()
    out = recommend_videos_tool(provider, account, top_n=top_n)
    assert out["error"]["code"] == "INVALID_ARGUMENT"
    assert provider.events == [] and account.events == []


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"account": None}, "ACCOUNT_NOT_AVAILABLE"),
        ({"liked": [], "subs": []}, "NOT_ENOUGH_HISTORY"),
        ({"read_error": AuthRequiredError("You are not signed in.")}, "AUTH_REQUIRED"),
    ],
)
def test_errors_have_a_code_and_a_fix(kwargs, code):
    provider, account = setup(**{k: v for k, v in kwargs.items() if k != "account"})
    out = recommend_videos_tool(provider, None if "account" in kwargs else account)
    assert out["error"]["code"] == code
    assert out["error"]["remediation"] and "Traceback" not in json.dumps(out)


def test_quota_error_is_reported():
    provider, account = setup()
    provider.budget_error = QuotaExceededError("needs 127")
    assert recommend_videos_tool(provider, account)["error"]["code"] == "QUOTA_EXCEEDED"


# --- over the real MCP protocol -------------------------------------------------------------------------------------------


def test_recommend_videos_over_the_protocol():
    provider, account = setup(candidates=[vid("new1", "Rust traits explained", channel="UC1")])
    server = create_server(provider, ProposalStore(Database(":memory:")), account)

    async def scenario():
        async with Client(server, mode="legacy") as client:
            tools = (await client.list_tools()).tools
            tool = next(t for t in tools if t.name == "recommend_videos")
            result = await client.call_tool("recommend_videos", {"top_n": 5})
            return tool, json.loads(result.content[0].text)

    tool, out = asyncio.run(scenario())
    assert tool.annotations.read_only_hint is True
    assert set(tool.input_schema["properties"]) == {"top_n"}
    assert out["results"][0]["title"] == "Rust traits explained"


def test_recommend_videos_without_an_account_over_the_protocol(provider):
    server = create_server(provider)  # fixture mode: no account

    async def scenario():
        async with Client(server, mode="legacy") as client:
            return json.loads((await client.call_tool("recommend_videos", {})).content[0].text)

    assert asyncio.run(scenario())["error"]["code"] == "ACCOUNT_NOT_AVAILABLE"


# --- found by a real test: a few tag-spammed videos and the word "shorts" dominated the profile ----------------------


def test_a_word_counts_once_per_liked_video_so_tag_spam_cannot_dominate():
    spam = vid("spam", "One clip", ["celebrity"] * 30)  # one video repeating a tag 30 times
    honest = [vid(f"f{n}", "Football highlights") for n in range(3)]
    profile = build_taste_profile([spam, *honest], [], [], term_count=3)
    # 3 videos beat 1 video, however often the tag repeats; the spammed tag is only a tie-break word
    assert profile.top_terms == ["football", "highlights", "celebrity"]


def test_format_words_are_not_interests():
    liked = [vid("a", "Funny moments #shorts", ["shorts", "viral"]), vid("b", "Football edit official video")]
    terms = build_taste_profile(liked, [], [], term_count=10).top_terms
    assert terms == ["football", "funny", "moments"]
    assert not {"shorts", "viral", "edit", "official", "video"} & set(terms)


def test_subscription_titles_are_also_counted_once_each():
    profile = build_taste_profile([], ["Rust Rust Rust", "Rust Lab", "Cooking"], [], term_count=2)
    assert profile.top_terms == ["rust", "cooking"]  # rust is in 2 titles however often it repeats; ties alphabetical
