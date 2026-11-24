import pytest

from ytmcp import proposals
from ytmcp.database import Database
from ytmcp.proposals import Proposal, ProposalStore, ProposedVideo, content_hash

NOW = 1_000_000.0


def make_proposal(pid="p1", status=proposals.PROPOSED, created=NOW, ttl=900):
    videos = (ProposedVideo("aaaaaaaaaaa", "Rust A", "Chan", 600), ProposedVideo("bbbbbbbbbbb", "Rust B", "Chan", 900))
    return Proposal(
        id=pid,
        content_hash=content_hash("Title", "Desc", ["aaaaaaaaaaa", "bbbbbbbbbbb"]),
        title="Title",
        description="Desc",
        videos=videos,
        constraints={"topic": "rust", "total_minutes": 25, "max_video_minutes": None, "language": None},
        created_at=created,
        expires_at=created + ttl,
        status=status,
    )


@pytest.fixture
def store():
    return ProposalStore(Database(":memory:"))


# --- content_hash ---------------------------------------------------------------------


def test_hash_is_short_hex_and_deterministic():
    h = content_hash("T", "D", ["a", "b"])
    assert h == content_hash("T", "D", ["a", "b"])
    assert len(h) == 16 and int(h, 16) >= 0


@pytest.mark.parametrize(
    "args",
    [("T2", "D", ["a", "b"]), ("T", "D2", ["a", "b"]), ("T", "D", ["b", "a"]), ("T", "D", ["a"]), ("T", "D", ["a", "b", "c"])],
)
def test_hash_changes_with_any_part_of_the_content(args):
    assert content_hash(*args) != content_hash("T", "D", ["a", "b"])


def test_proposal_ids_are_unique_and_unguessable():
    ids = {proposals.new_proposal_id() for _ in range(200)}
    assert len(ids) == 200
    assert all(len(i) >= 16 for i in ids)


def test_playlists_are_always_private():
    assert proposals.PRIVACY == "private"


# --- save and get -------------------------------------------------------------------------


def test_save_and_get_roundtrip(store):
    original = make_proposal()
    store.save(original)
    assert store.get("p1") == original


def test_unknown_id(store):
    assert store.get("nope") is None


def test_ids_are_used_as_values_not_as_sql(store):
    store.save(make_proposal())
    assert store.get("p1' OR '1'='1") is None
    assert store.get("p1'; DROP TABLE proposals; --") is None
    assert store.get("p1") is not None


def test_video_order_and_text_survive_storage(store):
    store.save(make_proposal())
    got = store.get("p1")
    assert [v.id for v in got.videos] == ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    assert got.videos[1] == ProposedVideo("bbbbbbbbbbb", "Rust B", "Chan", 900)


# --- confirm / claim / finish / decline (single use) --------------------------------------------


def test_confirm_works_once(store):
    store.save(make_proposal())
    assert store.confirm("p1", NOW + 10) is True
    assert store.get("p1").status == proposals.CONFIRMED
    assert store.confirm("p1", NOW + 10) is False


def test_confirm_refuses_an_expired_proposal(store):
    store.save(make_proposal())
    assert store.confirm("p1", NOW + 900) is False  # expiry moment itself counts as expired
    assert store.get("p1").status == proposals.PROPOSED


def test_confirm_refuses_an_unknown_proposal(store):
    assert store.confirm("nope", NOW) is False


def test_claim_from_the_right_status_only(store):
    store.save(make_proposal())
    assert store.claim("p1", NOW, proposals.CONFIRMED) is False  # it is "proposed", not "confirmed"
    assert store.claim("p1", NOW, proposals.PROPOSED) is True
    assert store.get("p1").status == proposals.CREATING


def test_claim_can_only_succeed_once(store):
    store.save(make_proposal())
    results = [store.claim("p1", NOW, proposals.PROPOSED) for _ in range(3)]
    assert results == [True, False, False]


def test_claim_from_confirmed(store):
    store.save(make_proposal())
    store.confirm("p1", NOW)
    assert store.claim("p1", NOW, proposals.CONFIRMED) is True


def test_claim_refuses_after_expiry(store):
    store.save(make_proposal())
    assert store.claim("p1", NOW + 900, proposals.PROPOSED) is False
    assert store.claim("p1", NOW + 899, proposals.PROPOSED) is True


def test_finish_records_status_and_playlist(store):
    store.save(make_proposal())
    store.claim("p1", NOW, proposals.PROPOSED)
    store.finish("p1", proposals.CREATED, "PL1")
    got = store.get("p1")
    assert (got.status, got.playlist_id) == (proposals.CREATED, "PL1")


def test_finish_only_works_on_a_proposal_being_created(store):
    store.save(make_proposal())
    store.finish("p1", proposals.CREATED, "PL1")  # never claimed: ignored
    assert store.get("p1").status == proposals.PROPOSED


def test_finish_without_a_playlist_keeps_it_empty(store):
    store.save(make_proposal())
    store.claim("p1", NOW, proposals.PROPOSED)
    store.finish("p1", proposals.FAILED)
    assert store.get("p1").playlist_id is None


@pytest.mark.parametrize("confirm_first", [False, True])
def test_decline_works_from_proposed_or_confirmed(store, confirm_first):
    store.save(make_proposal())
    if confirm_first:
        store.confirm("p1", NOW)
    assert store.decline("p1") is True
    assert store.get("p1").status == proposals.DECLINED


def test_a_declined_or_created_proposal_cannot_be_used_again(store):
    store.save(make_proposal(status=proposals.PROPOSED))
    store.decline("p1")
    assert store.claim("p1", NOW, proposals.PROPOSED) is False
    assert store.confirm("p1", NOW) is False
    store.save(make_proposal(pid="p2", status=proposals.CREATED))
    assert store.decline("p2") is False


# --- storage in the database file ------------------------------------------------------------------


def test_proposals_survive_a_restart_and_are_shared_between_connections(tmp_path):
    path = tmp_path / "ytmcp.db"
    ProposalStore(Database(path)).save(make_proposal())
    # a second connection (like the terminal command next to the running server) sees it and can change it
    other = ProposalStore(Database(path))
    assert other.get("p1") is not None
    assert other.confirm("p1", NOW) is True
    assert ProposalStore(Database(path)).get("p1").status == proposals.CONFIRMED


def test_old_proposals_are_deleted_at_startup(tmp_path):
    path = tmp_path / "ytmcp.db"
    cache = Database(path, now=lambda: NOW)
    store = ProposalStore(cache)
    store.save(make_proposal(pid="old", created=NOW - 2 * 24 * 3600))
    store.save(make_proposal(pid="new", created=NOW - 3600))
    cache.prune(24 * 3600, 3600)
    assert store.get("old") is None
    assert store.get("new") is not None
