"""SWAP SURFACE for api_tokens. Routes and the auth middleware import only
this module.

All five functions — create_token, list_tokens, revoke_token,
find_by_plaintext, touch_last_used — read/write ONE shared token store, so
they all dispatch through the same _provider() switch and MUST switch
together. find_by_plaintext/touch_last_used back the bearer-token auth
path in back_dev_home/_auth/middleware.py: a token created via office
create_token (Redis) has to be resolvable by an office find_by_plaintext,
or bearer auth silently breaks the instant
SKEWNONO_API_TOKENS_PROVIDER=office is set while only create/list/revoke
were wired to office. See MIGRATION.md's "Auth path" section.
"""

from back_dev_home._runtime.data_provider import get_data_provider


__all__ = [
    "create_token",
    "list_tokens",
    "revoke_token",
    "find_by_plaintext",
    "touch_last_used",
]


def _provider():
    if get_data_provider("api_tokens") == "office":
        from back_dev_home.api_tokens.providers import office
        return office
    from back_dev_home.api_tokens.providers import mock
    return mock


def create_token(owner_user_id: str, label: str) -> tuple[dict, str]:
    return _provider().create_token(owner_user_id, label)


def list_tokens(owner_user_id: str) -> list[dict]:
    return _provider().list_tokens(owner_user_id)


def revoke_token(owner_user_id: str, token_id: str) -> bool:
    return _provider().revoke_token(owner_user_id, token_id)


def find_by_plaintext(plaintext: str):
    """Resolve a bearer-token plaintext to its owning row, or None.

    Signature/behavior copied verbatim from the old (pre-seam) data.py.
    Called on every /api/* request carrying an
    ``Authorization: Bearer skn_...`` header
    (back_dev_home/_auth/middleware.py::_try_api_token). The mock provider
    returns its private ``_TokenRow`` dataclass instance (or ``None``);
    middleware only reads ``row.owner_user_id`` and ``row.id`` off it (not
    dict keys), so any provider implementing this must return ``None`` or
    an object exposing at least those two attributes.
    """
    return _provider().find_by_plaintext(plaintext)


def touch_last_used(token_id: str) -> None:
    """Record that a bearer token was just used to authenticate a request.

    Signature/behavior copied verbatim from the old (pre-seam) data.py.
    Called once per authenticated bearer request via
    back_dev_home/_auth/middleware.py::_try_api_token, right after
    find_by_plaintext resolves the token — i.e. on every request, not just
    on token creation. The mock provider debounces the actual write to
    once per minute per token; see MIGRATION.md.
    """
    return _provider().touch_last_used(token_id)
