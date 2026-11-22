import pytest
from fake_auth import BrokenKeyring, MemoryKeyring, make_token

from ytmcp.auth.tokens import SERVICE, USERNAME, Token, TokenStore
from ytmcp.errors import AuthFailedError


def test_json_roundtrip():
    token = make_token()
    assert Token.from_json(token.to_json()) == token


def test_roundtrip_without_refresh_token():
    token = make_token(refresh=None)
    assert Token.from_json(token.to_json()) == token


def test_expired_uses_a_safety_margin():
    token = make_token(expires_at=1000.0)
    assert token.expired(now=1000.0)
    assert token.expired(now=941.0)  # within 60 s of the end
    assert not token.expired(now=900.0)


def test_repr_hides_secrets():
    text = repr(make_token())
    assert "ACCESS-1" not in text and "REFRESH-1" not in text


def test_save_and_load():
    store = TokenStore(MemoryKeyring())
    assert store.load() is None
    store.save(make_token())
    assert store.load() == make_token()


def test_token_is_stored_under_one_keyring_entry():
    keyring = MemoryKeyring()
    TokenStore(keyring).save(make_token())
    assert list(keyring.items) == [(SERVICE, USERNAME)]


def test_delete():
    store = TokenStore(MemoryKeyring())
    assert store.delete() is False
    store.save(make_token())
    assert store.delete() is True
    assert store.load() is None


def test_damaged_entry_counts_as_signed_out():
    keyring = MemoryKeyring()
    keyring.set_password(SERVICE, USERNAME, "not json")
    assert TokenStore(keyring).load() is None


@pytest.mark.parametrize("action", ["load", "delete"])
def test_missing_keyring_gives_a_clear_error(action):
    with pytest.raises(AuthFailedError) as exc:
        getattr(TokenStore(BrokenKeyring()), action)()
    assert "keyring" in str(exc.value)


def test_missing_keyring_error_on_save():
    with pytest.raises(AuthFailedError):
        TokenStore(BrokenKeyring()).save(make_token())


def test_tokens_are_never_written_to_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    TokenStore(MemoryKeyring()).save(make_token())
    assert list(tmp_path.iterdir()) == []
