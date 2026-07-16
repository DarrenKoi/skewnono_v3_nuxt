"""SWAP SURFACE for api_tokens. Routes import only this module.

find_by_plaintext and touch_last_used are re-exported from providers/mock
unconditionally (mock-only by design, like activity's is_recordable /
seed_demo_users) — they back the bearer-token auth path in
back_dev_home/_auth/middleware.py, which must keep resolving tokens from
the same in-memory store that create_token/list_tokens/revoke_token use in
mock mode, independent of SKEWNONO_API_TOKENS_PROVIDER.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.api_tokens.providers.mock import (
    find_by_plaintext,  # mock-only: shares the in-memory store w/ auth middleware
    touch_last_used,     # mock-only: same reason
)


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
