"""FR-4: statistics, arguments, the analysis, the tool, and the tool over the real MCP protocol."""

import asyncio
import json
from datetime import UTC, datetime

import pytest
from fake_playlists import FakeAccount
from mcp import Client

from ytmcp.database import Database
from ytmcp.errors import AuthRequiredError, QuotaExceededError
from ytmcp.models import LikedVideo, Subscription, Video
from ytmcp.proposals import ProposalStore
from ytmcp.providers.base import VideoProvider
from ytmcp.server import create_server
from ytmcp.services.engagement import (
    DATE_FIELD,
    LIKES_CAP,
    PLAYLISTS_CAP,
    SUBSCRIPTIONS_CAP,
    WATCH_HISTORY_NOTE,
    analyze_engagement,
    compare_periods,
    duration_buckets,
    estimate_cost,
    monthly_trend,
    top_counts,
    validate_arguments,
)
from ytmcp.tools import analyze_engagement_tool

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def vid(vid_id, channel="UC1", channel_title="Chan One", category="27", seconds=600):
    return Video(
        id=vid_id, title=f"Video {vid_id}", description="", channel_id=channel,
        channel_title=channel_title, category_id=category, duration_seconds=seconds,
    )


def like(video_id, when):
    return LikedVideo(video_id, when)


class EngagementProvider(VideoProvider):
    """Records what it is asked. get_videos answers from `details`."""

    def __init__(self, details=(), categories=None, budget_error=None):
        self.details = {v.id: v for v in details}
        self.categories = categories if categories is not None else {"27": "Education", "26": "Howto & Style"}
        self.budget_error = budget_error
        self.events: list[tuple] = []

    def ensure_budget(self, units):
        self.events.append(("budget", units))
        if self.budget_error:
            raise self.budget_error

    def get_videos(self, video_ids):
        self.events.append(("get_videos", list(video_ids)))
        return [self.details[i] for i in video_ids if i in self.details]

    def category_names(self, region="US"):
        self.events.append(("categories", region))
        return dict(self.categories)

    def search_videos(self, query, max_results=25):
        return []

    def get_channels(self, channel_ids):
        return []

    def get_channel_by_handle(self, handle):
        return None

    def search_channels(self, query, max_results=25):
        return []

    def get_recent_uploads(self, channel_id, max_results=10):
        return []

    def kinds(self):
        return [event[0] for event in self.events]


# --- top_counts (FR-4.1) ----------------------------------------------------------------------------


def test_top_counts_gives_count_and_share_most_common_first():
    out = top_counts(["a", "b", "a", "c", "a", "b"])
    assert out == [
        {"name": "a", "count": 3, "share": 0.5},
        {"name": "b", "count": 2, "share": 0.333},
        {"name": "c", "count": 1, "share": 0.167},
    ]


def test_ties_are_ordered_by_name_not_by_key():
    names = {"k1": "Zebra", "k2": "Apple"}
    assert [e["name"] for e in top_counts(["k1", "k2"], names=names)] == ["Apple", "Zebra"]


def test_top_counts_limits_to_n_and_handles_nothing():
    assert len(top_counts([str(n) for n in range(30)], n=5)) == 5
    assert top_counts([]) == []


def test_a_key_without_a_name_shows_the_key():
    assert top_counts(["x"], names={"y": "Why"})[0]["name"] == "x"


def test_extra_fields_are_added_to_each_entry():
    out = top_counts(["a", "b"], extra=lambda key: {"flag": key == "a"})
    assert [(e["name"], e["flag"]) for e in out] == [("a", True), ("b", False)]


# --- duration buckets (FR-4.3) -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seconds, bucket",
    [(0, "under 5 min"), (299, "under 5 min"), (300, "5 to 20 min"), (1199, "5 to 20 min"),
     (1200, "20 to 60 min"), (3599, "20 to 60 min"), (3600, "over 60 min"), (90000, "over 60 min")],
)
def test_bucket_edges(seconds, bucket):
    counts = {b["bucket"]: b["count"] for b in duration_buckets([vid("a", seconds=seconds)])}
    assert counts[bucket] == 1 and sum(counts.values()) == 1


def test_buckets_always_list_all_four_in_order_with_shares():
    out = duration_buckets([vid("a", seconds=60), vid("b", seconds=60), vid("c", seconds=400), vid("d", seconds=5000)])
    assert [b["bucket"] for b in out] == ["under 5 min", "5 to 20 min", "20 to 60 min", "over 60 min"]
    assert [b["share"] for b in out] == [0.5, 0.25, 0.0, 0.25]


def test_no_videos_gives_four_empty_buckets():
    assert [b["count"] for b in duration_buckets([])] == [0, 0, 0, 0]
    assert all(b["share"] == 0.0 for b in duration_buckets([]))


# --- monthly trend (FR-4.2) ------------------------------------------------------------------------------


def test_months_are_zero_filled_oldest_first():
    out = monthly_trend([like("a", "2026-11-05T10:00:00Z"), like("b", "2026-09-01T00:00:00Z")], 3, NOW)
    assert out == [{"month": "2026-09", "likes": 1}, {"month": "2026-10", "likes": 0}, {"month": "2026-11", "likes": 1}]


def test_month_boundaries_are_exact_utc():
    out = monthly_trend([like("a", "2026-11-01T00:00:00Z"), like("b", "2026-10-31T23:59:59Z")], 2, NOW)
    assert out == [{"month": "2026-10", "likes": 1}, {"month": "2026-11", "likes": 1}]


def test_a_time_zone_offset_is_converted_to_utc():
    out = monthly_trend([like("a", "2026-11-01T01:00:00+05:00")], 2, NOW)  # that is still 31 October in UTC
    assert out == [{"month": "2026-10", "likes": 1}, {"month": "2026-11", "likes": 0}]


def test_one_month_is_just_this_month():
    out = monthly_trend([like("a", "2026-11-02T00:00:00Z"), like("b", "2026-10-02T00:00:00Z")], 1, NOW)
    assert out == [{"month": "2026-11", "likes": 1}]


def test_the_range_crosses_a_year_boundary():
    out = monthly_trend([], 4, datetime(2026, 2, 10, tzinfo=UTC))
    assert [m["month"] for m in out] == ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_likes_before_the_period_after_it_or_without_a_date_are_ignored():
    liked = [like("old", "2020-01-01T00:00:00Z"), like("future", "2027-01-01T00:00:00Z"), like("bad", "not a date"), like("empty", "")]
    assert sum(m["likes"] for m in monthly_trend(liked, 12, NOW)) == 0


def test_a_sixty_month_period_has_sixty_entries():
    assert len(monthly_trend([], 60, NOW)) == 60


# --- compare two periods (FR-4.3) ---------------------------------------------------------------------------


def test_compare_uses_the_last_n_months_and_the_n_before():
    liked = [
        like("a", "2026-11-10T00:00:00Z"), like("b", "2026-09-01T00:00:00Z"),  # current: 2026-09 to 2026-11
        like("c", "2026-08-31T23:59:59Z"), like("d", "2026-06-01T00:00:00Z"),  # previous: 2026-06 to 2026-08
        like("e", "2026-05-31T23:59:59Z"),  # before both windows
    ]
    details = {k: vid(k, channel=f"UC{k}", channel_title=f"Chan {k}") for k in "abcde"}
    out = compare_periods(liked, details, 3, NOW, {"27": "Education"})
    assert (out["current"]["from"], out["current"]["to"], out["current"]["likes"]) == ("2026-09", "2026-11", 2)
    assert (out["previous"]["from"], out["previous"]["to"], out["previous"]["likes"]) == ("2026-06", "2026-08", 2)
    assert {c["name"] for c in out["current"]["top_channels"]} == {"Chan a", "Chan b"}
    assert {c["name"] for c in out["previous"]["top_channels"]} == {"Chan c", "Chan d"}


def test_each_window_has_its_own_lists_and_buckets_with_names():
    liked = [like("a", "2026-11-10T00:00:00Z"), like("b", "2026-08-10T00:00:00Z")]
    details = {"a": vid("a", category="27", seconds=100), "b": vid("b", category="26", seconds=4000)}
    out = compare_periods(liked, details, 3, NOW, {"27": "Education", "26": "Howto & Style"})
    assert out["current"]["top_categories"][0]["name"] == "Education"
    assert out["previous"]["top_categories"][0]["name"] == "Howto & Style"
    assert out["current"]["duration_preferences"][0]["count"] == 1  # under 5 min
    assert out["previous"]["duration_preferences"][3]["count"] == 1  # over 60 min


def test_compare_counts_a_like_even_when_its_details_are_missing():
    out = compare_periods([like("gone", "2026-11-10T00:00:00Z")], {}, 3, NOW, {})
    assert out["current"]["likes"] == 1 and out["current"]["top_channels"] == []


def test_compare_lists_are_short():
    liked = [like(f"v{n}", "2026-11-10T00:00:00Z") for n in range(8)]
    details = {f"v{n}": vid(f"v{n}", channel=f"UC{n}", channel_title=f"Chan {n}") for n in range(8)}
    assert len(compare_periods(liked, details, 3, NOW, {})["current"]["top_channels"]) == 5


# --- arguments (FR-4) -------------------------------------------------------------------------------------------


def fields_of(**kwargs):
    from ytmcp.errors import InvalidArgumentError

    with pytest.raises(InvalidArgumentError) as exc:
        validate_arguments(**kwargs)
    return exc.value.fields


def test_defaults_are_all_sources_twelve_months_no_compare():
    args = validate_arguments()
    assert (args.sources, args.period_months, args.compare) == (("likes", "subscriptions", "playlists"), 12, False)


def test_sources_are_kept_in_a_fixed_order_without_duplicates():
    assert validate_arguments(sources=["playlists", "likes", "playlists"]).sources == ("likes", "playlists")


@pytest.mark.parametrize("sources", [[], "likes", ["videos"], ["likes", 5], 5, ["likes", "watch_history"]])
def test_bad_sources(sources):
    assert "sources" in fields_of(sources=sources)


def test_unknown_sources_are_named():
    assert "watch_history" in fields_of(sources=["likes", "watch_history"])["sources"]


@pytest.mark.parametrize("months", [1, 12, 60])
def test_period_limits_are_inclusive(months):
    assert validate_arguments(period_months=months).period_months == months


@pytest.mark.parametrize("months", [0, -1, 61, "12", 12.5, True, None])
def test_bad_period_months(months):
    assert "period_months" in fields_of(period_months=months)


@pytest.mark.parametrize("compare", ["yes", 1, 0, None])
def test_compare_must_be_a_real_true_or_false(compare):
    assert "compare" in fields_of(compare=compare)


def test_compare_needs_likes_because_only_likes_have_a_date():
    assert "likes" in fields_of(sources=["subscriptions"], compare=True)["compare"]
    assert validate_arguments(sources=["likes"], compare=True).compare is True


def test_all_problems_are_reported_together():
    assert set(fields_of(sources=[], period_months=0, compare="x")) == {"sources", "period_months", "compare"}


# --- cost ---------------------------------------------------------------------------------------------------------


def test_cost_with_everything_is_47_units():
    assert estimate_cost() == 47
    assert 1 + 10 + 4 + 1 + 10 + 10 + 10 + 1 == 47
    assert (LIKES_CAP, SUBSCRIPTIONS_CAP, PLAYLISTS_CAP) == (500, 200, 10)


@pytest.mark.parametrize(
    "sources, cost",
    [(("likes",), 22), (("subscriptions",), 4), (("playlists",), 22), (("likes", "subscriptions"), 26)],
)
def test_cost_follows_the_chosen_sources(sources, cost):
    assert estimate_cost(sources) == cost


# --- the analysis ---------------------------------------------------------------------------------------------------


def setup(liked=(), subs=(), playlist_ids=(), details=(), **kwargs):
    return EngagementProvider(details=details, **{k: v for k, v in kwargs.items() if k in ("categories", "budget_error")}), FakeAccount(
        liked=list(liked), subscribed=list(subs), playlist_ids=set(playlist_ids),
        **{k: v for k, v in kwargs.items() if k == "read_error"},
    )


def run(provider, account, **kwargs):
    return analyze_engagement(provider, account, validate_arguments(**kwargs), NOW)


FULL = {
    "liked": [like("a", "2026-11-05T00:00:00Z"), like("b", "2026-10-05T00:00:00Z"), like("c", "2026-10-06T00:00:00Z")],
    "subs": [Subscription("UC1", "Chan One"), Subscription("UC9", "Only Subscribed")],
    "playlist_ids": {"p1", "a"},  # "a" is also liked
    "details": [
        vid("a", "UC1", "Chan One", "27", 200), vid("b", "UC2", "Chan Two", "26", 700),
        vid("c", "UC2", "Chan Two", None, 4000), vid("p1", "UC3", "Chan Three", "99", 100),
    ],
}


def test_the_report_shape():
    report = run(*setup(**FULL))
    assert set(report) == {"sources", "period_months", "totals", "top_channels", "top_categories", "duration_preferences", "monthly_trend", "caveats", "note"}
    assert report["sources"] == ["likes", "subscriptions", "playlists"] and report["period_months"] == 12
    assert report["totals"] == {"likes": 3, "subscriptions": 2, "playlist_videos": 2}
    assert report["note"] == WATCH_HISTORY_NOTE == "Based on your likes, subscriptions and playlists only. YouTube does not share watch history."
    assert report["monthly_trend"]["date_field"] == DATE_FIELD
    assert "comparison" not in report


def test_every_liked_video_saved_video_and_subscription_counts_once_for_its_channel():
    channels = {c["name"]: c for c in run(*setup(**FULL))["top_channels"]}
    # a video both liked and saved counts once: Chan One has video a (1) + a subscription (1)
    assert channels["Chan One"]["count"] == 2 and channels["Chan Two"]["count"] == 2
    assert channels["Chan Three"]["count"] == 1 and channels["Only Subscribed"]["count"] == 1
    assert sum(c["count"] for c in channels.values()) == 6  # 4 distinct videos + 2 subscriptions
    assert channels["Chan One"]["share"] == round(2 / 6, 3)


def test_top_channels_say_which_ones_you_subscribe_to():
    channels = {c["name"]: c["subscribed"] for c in run(*setup(**FULL))["top_channels"]}
    assert channels == {"Chan One": True, "Chan Two": False, "Chan Three": False, "Only Subscribed": True}


def test_categories_use_the_names_and_label_the_unknown_ones():
    cats = {c["name"]: c["count"] for c in run(*setup(**FULL))["top_categories"]}
    assert cats == {"Education": 1, "Howto & Style": 1, "Unknown": 1, "Category 99": 1}


def test_categories_are_asked_for_once_and_only_when_there_are_videos():
    provider, account = setup(**FULL)
    run(provider, account)
    assert provider.kinds().count("categories") == 1
    provider, account = setup(subs=[Subscription("UC1", "Chan One")])
    run(provider, account, sources=["subscriptions"])
    assert "categories" not in provider.kinds() and "get_videos" not in provider.kinds()


def test_duration_preferences_cover_the_liked_and_saved_videos():
    buckets = {b["bucket"]: b["count"] for b in run(*setup(**FULL))["duration_preferences"]}
    assert buckets == {"under 5 min": 2, "5 to 20 min": 1, "20 to 60 min": 0, "over 60 min": 1}


def test_the_monthly_trend_counts_likes_by_the_date_liked():
    months = {m["month"]: m["likes"] for m in run(*setup(**FULL), period_months=3)["monthly_trend"]["months"]}
    assert months == {"2026-09": 0, "2026-10": 2, "2026-11": 1}


def test_compare_adds_both_windows():
    report = run(*setup(**FULL), period_months=1, compare=True)
    assert report["comparison"]["current"]["likes"] == 1 and report["comparison"]["previous"]["likes"] == 2


def test_only_the_chosen_sources_are_read():
    provider, account = setup(**FULL)
    report = run(provider, account, sources=["likes"])
    assert [e[0] for e in account.events] == ["liked"]
    assert report["totals"] == {"likes": 3, "subscriptions": 0, "playlist_videos": 0}
    assert all("subscribed" not in c for c in report["top_channels"])  # no flag without that source


def test_without_likes_there_is_no_trend_because_only_likes_have_a_date():
    report = run(*setup(**FULL), sources=["subscriptions", "playlists"])
    assert "monthly_trend" not in report and "comparison" not in report


def test_subscriptions_alone_still_give_a_channel_list():
    report = run(*setup(subs=[Subscription("UC1", "One"), Subscription("UC2", "Two")]), sources=["subscriptions"])
    assert [c["name"] for c in report["top_channels"]] == ["One", "Two"]
    assert report["top_categories"] == [] and report["totals"]["subscriptions"] == 2


def test_the_caps_are_passed_exactly():
    provider, account = setup(**FULL)
    run(provider, account)
    assert ("liked", 500) in account.events and ("subscriptions", 200) in account.events and ("playlists", 10) in account.events


def test_the_budget_is_checked_first_with_the_cost_of_the_chosen_sources():
    provider, account = setup(**FULL)
    run(provider, account)
    assert provider.events[0] == ("budget", 47)
    provider, account = setup(**FULL)
    run(provider, account, sources=["likes"])
    assert provider.events[0] == ("budget", 22)


def test_when_the_budget_is_short_nothing_about_the_account_is_read():
    provider, account = setup(**FULL, budget_error=QuotaExceededError("needs 47"))
    with pytest.raises(QuotaExceededError):
        run(provider, account)
    assert provider.events == [("budget", 47)] and account.events == []


def test_without_an_account_nothing_is_called():
    from ytmcp.errors import AccountUnavailableError

    provider = EngagementProvider()
    with pytest.raises(AccountUnavailableError):
        analyze_engagement(provider, None, validate_arguments(), NOW)
    assert provider.events == []


def test_not_signed_in_passes_through():
    provider, account = setup(read_error=AuthRequiredError("You are not signed in."), **FULL)
    with pytest.raises(AuthRequiredError) as exc:
        run(provider, account)
    assert exc.value.code == "AUTH_REQUIRED"
    assert "get_videos" not in provider.kinds()


def test_empty_sources_are_not_enough_history():
    from ytmcp.errors import NotEnoughHistoryError

    with pytest.raises(NotEnoughHistoryError):
        run(*setup())


def test_the_same_input_gives_the_same_report():
    assert run(*setup(**FULL), compare=True) == run(*setup(**FULL), compare=True)


# --- coverage caveats ----------------------------------------------------------------------------------------------------


def many_likes(count, newest="2026-11-10T00:00:00Z", oldest="2026-09-01T00:00:00Z"):
    out = [like(f"v{n}", newest) for n in range(count - 1)]
    return [*out, like("last", oldest)]


def test_a_cut_off_period_is_called_out():
    liked = many_likes(500)  # the cap, and the oldest read like is 1 September
    report = run(*setup(liked=liked, details=[]), sources=["likes"], period_months=12)
    assert report["caveats"] == ["Only your newest 500 likes were read (back to 2026-09-01), so earlier months are incomplete."]


def test_no_caveat_when_the_cap_was_not_reached_or_the_period_is_covered():
    assert run(*setup(liked=many_likes(499)), sources=["likes"])["caveats"] == []
    assert run(*setup(liked=many_likes(500)), sources=["likes"], period_months=2)["caveats"] == []  # 2 months fits inside the data


def test_a_comparison_needs_twice_the_period_to_be_covered():
    liked = many_likes(500, oldest="2026-04-01T00:00:00Z")  # covers 8 months
    assert run(*setup(liked=liked), sources=["likes"], period_months=6)["caveats"] == []
    assert len(run(*setup(liked=liked), sources=["likes"], period_months=6, compare=True)["caveats"]) == 1


def test_the_subscription_cap_is_called_out():
    subs = [Subscription(f"UC{n}", f"C{n}") for n in range(200)]
    assert run(*setup(subs=subs), sources=["subscriptions"])["caveats"] == ["Only the first 200 subscriptions were read."]


def test_likes_with_no_usable_dates_give_no_caveat():
    liked = [like(f"v{n}", "") for n in range(500)]
    assert run(*setup(liked=liked), sources=["likes"])["caveats"] == []


# --- the tool --------------------------------------------------------------------------------------------------------------


def test_the_tool_returns_the_report():
    out = analyze_engagement_tool(*setup(**FULL), now=NOW)
    assert out["totals"]["likes"] == 3 and out["note"] == WATCH_HISTORY_NOTE


@pytest.mark.parametrize(
    "kwargs, field",
    [({"sources": ["nope"]}, "sources"), ({"period_months": 0}, "period_months"), ({"compare": "yes"}, "compare")],
)
def test_invalid_arguments_give_field_errors_and_make_no_call(kwargs, field):
    provider, account = setup(**FULL)
    out = analyze_engagement_tool(provider, account, now=NOW, **kwargs)
    assert out["error"]["code"] == "INVALID_ARGUMENT" and field in out["error"]["fields"]
    assert out["error"]["remediation"]
    assert provider.events == [] and account.events == []


@pytest.mark.parametrize(
    "build, code",
    [
        (lambda: (EngagementProvider(), None), "ACCOUNT_NOT_AVAILABLE"),
        (lambda: setup(read_error=AuthRequiredError("You are not signed in.")), "AUTH_REQUIRED"),
        (lambda: setup(), "NOT_ENOUGH_HISTORY"),
        (lambda: setup(**FULL, budget_error=QuotaExceededError("needs 47")), "QUOTA_EXCEEDED"),
    ],
)
def test_errors_have_a_code_and_a_fix(build, code):
    provider, account = build()
    out = analyze_engagement_tool(provider, account, now=NOW)
    assert out["error"]["code"] == code and out["error"]["remediation"]
    assert "Traceback" not in json.dumps(out)


def test_the_tool_does_not_list_individual_liked_videos():
    text = json.dumps(analyze_engagement_tool(*setup(**FULL), now=NOW))
    assert "Video a" not in text and "Video b" not in text  # only aggregates, never the titles


# --- over the real MCP protocol ----------------------------------------------------------------------------------------------


def test_analyze_engagement_over_the_protocol():
    provider, account = setup(**FULL)
    server = create_server(provider, ProposalStore(Database(":memory:")), account)

    async def scenario():
        async with Client(server, mode="legacy") as client:
            tool = next(t for t in (await client.list_tools()).tools if t.name == "analyze_engagement")
            ok = json.loads((await client.call_tool("analyze_engagement", {"sources": ["likes"], "period_months": 3})).content[0].text)
            bad = json.loads((await client.call_tool("analyze_engagement", {"period_months": 99})).content[0].text)
            return tool, ok, bad

    tool, ok, bad = asyncio.run(scenario())
    assert tool.annotations.read_only_hint is True
    assert set(tool.input_schema["properties"]) == {"sources", "period_months", "compare"}
    assert ok["sources"] == ["likes"] and len(ok["monthly_trend"]["months"]) == 3
    assert bad["error"]["code"] == "INVALID_ARGUMENT"


def test_analyze_engagement_without_an_account_over_the_protocol(provider):
    server = create_server(provider)  # fixture mode: no account

    async def scenario():
        async with Client(server, mode="legacy") as client:
            return json.loads((await client.call_tool("analyze_engagement", {})).content[0].text)

    assert asyncio.run(scenario())["error"]["code"] == "ACCOUNT_NOT_AVAILABLE"
