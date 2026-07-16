"""Stable response contracts for api_tokens endpoints."""

from __future__ import annotations

from typing import TypedDict


__all__ = ["TokenRow", "TokenListResponse", "CreateTokenResponse"]


class TokenRow(TypedDict):
    id: str
    label: str
    created_at: str
    last_used_at: str | None


# list_tokens(owner_user_id) returns a bare list of TokenRow — no wrapping
# object. routes.py wraps it as {"tokens": [...]} for the GET response body.
TokenListResponse = list[TokenRow]


class CreateTokenResponse(TypedDict):
    token: TokenRow
    plaintext: str
