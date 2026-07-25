"""Contract gate for api_tokens. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/api_tokens
Office: SKEWNONO_API_TOKENS_PROVIDER=office .venv/bin/pytest back_dev_home/api_tokens

Provider-safe roundtrip: create_token/revoke_token create and then revoke
their own token, so this test cleans up after itself regardless of which
provider is active.

Nothing here is fenced behind the provider. The roundtrip supplies its own data
instead of reading fabricated rows, so every assertion below is a rule
MIGRATION.md requires of the office adapter too — an owner's list shape, the
one-time-plaintext response shape, find_by_plaintext resolving a freshly created
secret (and missing on both rejection paths), and revoke returning True once.
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.api_tokens import data
from back_dev_home.api_tokens.contracts import CreateTokenResponse, TokenListResponse


def test_list_tokens_matches_contract():
    assert_matches(data.list_tokens("contract-gate-user"), TokenListResponse)


def test_create_then_revoke_roundtrip():
    # create_token's real signature returns (public view, plaintext) — a
    # tuple, not a dict — so it is reassembled here into the shape the
    # POST /api/account/api-tokens response actually sends over the wire
    # (routes.py does the same reassembly) before checking it against
    # CreateTokenResponse.
    view, plaintext = data.create_token("contract-gate-user", "contract-gate-token")
    try:
        payload = {"token": view, "plaintext": plaintext}
        assert_matches(payload, CreateTokenResponse)

        # Bearer-auth path (store-coupled): the freshly-created plaintext must
        # resolve to a token, a bogus secret must not, and the last-used write
        # must not raise. A CRUD-only gate would miss that these enforcement
        # functions were switched alongside create/revoke.
        assert data.find_by_plaintext(plaintext) is not None
        # Both rejection paths: a wrong prefix short-circuits before any lookup,
        # while a secret carrying the real prefix ("skn_", MIGRATION.md) must
        # actually miss the hash index — a store that resolves either one is
        # broken, and only the second case exercises the lookup at all.
        assert data.find_by_plaintext("nope_not-a-real-token") is None
        assert data.find_by_plaintext("skn_not-a-real-token") is None
        data.touch_last_used(view["id"])
    finally:
        token_id = view["id"]
        assert data.revoke_token("contract-gate-user", token_id) is True
