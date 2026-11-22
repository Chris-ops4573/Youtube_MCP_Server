from ytmcp.auth import pkce


def test_challenge_matches_rfc_7636_example():
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert pkce.challenge_for(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_verifier_length_is_allowed_and_random():
    a, b = pkce.new_verifier(), pkce.new_verifier()
    assert 43 <= len(a) <= 128
    assert a != b


def test_challenge_has_no_padding_or_unsafe_characters():
    challenge = pkce.challenge_for(pkce.new_verifier())
    assert "=" not in challenge and "+" not in challenge and "/" not in challenge
    assert len(challenge) == 43


def test_state_is_random():
    assert pkce.new_state() != pkce.new_state()
    assert len(pkce.new_state()) >= 32
