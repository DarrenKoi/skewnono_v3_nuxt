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


def require_admin(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin(getattr(g, "user_id", None)):
            return error_json("forbidden", "admin access required", 403)
        return view(*args, **kwargs)

    return wrapper
