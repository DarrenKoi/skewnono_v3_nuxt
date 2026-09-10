"""Shared admin identity check.

One allowlist decides who may use admin surfaces (activity admin panel,
/api/admin/*). Defaults are phase-aware so no env setup is needed:
local-dev at home, member 2067928 in the cloud. SKEWNONO_ADMIN_USERS
(comma-separated) overrides both.

Member-id comparison is case-insensitive, matching the access-control
rule layer — otherwise an X-prefixed admin whose SSO id case differs
from the allowlist would be locked out of the very page that fixes it.
"""

from __future__ import annotations

import os
from functools import lru_cache, wraps

from flask import g

from .._runtime.env import is_cloud
from .errors import error_json
from .provider import SOURCE_COOKIE, SOURCE_LOCAL, SOURCE_TOKEN

_CLOUD_DEFAULT_ADMINS = frozenset({"2067928"})
_HOME_DEFAULT_ADMINS = frozenset({"LOCAL-DEV"})


# Keyed on the raw env value so a changed SKEWNONO_ADMIN_USERS (tests, config
# reload) is picked up while steady-state requests skip the re-parse.
@lru_cache(maxsize=8)
def _parse_allowlist(raw: str, cloud: bool) -> frozenset[str]:
    members = {part.strip().upper() for part in raw.split(",") if part.strip()}
    if members:
        return frozenset(members)
    return _CLOUD_DEFAULT_ADMINS if cloud else _HOME_DEFAULT_ADMINS


def _admin_allowlist() -> frozenset[str]:
    return _parse_allowlist(os.environ.get("SKEWNONO_ADMIN_USERS", ""), is_cloud())


def is_admin(user_id: str | None) -> bool:
    if not user_id or user_id == "-":
        return False
    return user_id.strip().upper() in _admin_allowlist()


# Which identity sources may hold admin. A WHITELIST: a step added to the
# identity chain later holds no admin until it is deliberately named here.
#
# `local` is in the set because home's fallback id, `local-dev`, is itself an
# admin id — and the provider that produces it is installed only when
# is_cloud() is false, so `local` cannot appear on the cloud at all.
#
# `declared` and `anonymous` are out, and those two exclusions are the entire
# server-side security boundary of the self-identification feature: the gate
# that routes anonymous callers to the form is client-side and bypassable, so
# this is the one rule an attacker cannot skip past.
_TRUSTED_SOURCES = frozenset({SOURCE_TOKEN, SOURCE_COOKIE, SOURCE_LOCAL})


def is_admin_request() -> bool:
    """Is the CALLER of this request an admin?

    Not the same question as `is_admin`, which answers "is this id an admin" —
    true for a self-declared identity that typed an admin's employee number
    without proving anything. Every admin gate uses this one; `is_admin` stays
    a pure id check for the callers that genuinely have only an id.
    """
    if getattr(g, "identity_source", None) not in _TRUSTED_SOURCES:
        return False
    return is_admin(getattr(g, "user_id", None))


def require_admin(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin_request():
            return error_json("forbidden", "admin access required", 403)
        return view(*args, **kwargs)

    return wrapper
