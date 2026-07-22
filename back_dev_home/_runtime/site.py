"""Where is this process running — home or office?

The deployment site decides the *default* data provider so the step-by-step
mock→office transition needs no .env editing on either machine:

* home Mac mini  -> mock mode (Phase 1)
* office machine -> office mode; WHICH features that actually flips is a
  separate question, answered by whether each has a providers/office.py
  (``office_registry``) — a blanket office default would 500 every feature
  whose adapter is not written yet
* unknown host   -> mock (safe: never assume office infrastructure exists)

Detection order:

1. ``SKEWNONO_SITE`` env var (``home`` | ``office``) — the explicit override,
   useful for testing office adapters from home over VPN.
2. Cloud deploy path (``env.is_cloud()``): Phase 3 production runs inside the
   company network, so it counts as ``office``. Path-based, so production can
   never fall back to mock because a VM hostname changed.
3. Hostname match. Home hostnames are tracked here; office hostnames come
   from ``SKEWNONO_OFFICE_HOSTNAMES`` (comma-separated, set once in the
   office machine's .env) or the tracked set below once known.

Explicit ``SKEWNONO_<FEATURE>_PROVIDER`` / ``SKEWNONO_DATA_PROVIDER`` env
vars always beat the site default — see ``data_provider.py``.
"""

import os
import socket
from typing import Literal

from back_dev_home._runtime.env import is_cloud


Site = Literal["home", "office"]

_SITE_ENV = "SKEWNONO_SITE"
_OFFICE_HOSTS_ENV = "SKEWNONO_OFFICE_HOSTNAMES"

# Hostnames are compared lowercased with any domain suffix (".local", ...)
# stripped, so "Daeyoungs-Mac-mini.local" matches "daeyoungs-mac-mini".
_HOME_HOSTNAMES = frozenset({"daeyoungs-mac-mini"})
# Company-issued office PCs are named "PC<...>" — that prefix IS the office
# signal, so no per-machine registration is needed. SKEWNONO_OFFICE_HOSTNAMES
# remains for any office machine that breaks the naming convention.
_OFFICE_HOST_PREFIX = "pc"
_OFFICE_HOSTNAMES = frozenset()


def _normalize_host(name: str) -> str:
    return name.strip().lower().split(".", 1)[0]


def detect_site() -> Site | None:
    """The current site, or None when it cannot be determined."""
    explicit = (os.environ.get(_SITE_ENV) or "").strip().lower()
    if explicit in ("home", "office"):
        return explicit  # type: ignore[return-value]
    if explicit:
        raise RuntimeError(
            f"Invalid {_SITE_ENV}={explicit!r}; expected 'home' or 'office'."
        )

    if is_cloud():
        return "office"

    host = _normalize_host(socket.gethostname())
    if host in _HOME_HOSTNAMES:
        return "home"
    if host.startswith(_OFFICE_HOST_PREFIX):
        return "office"

    office_hosts = {
        _normalize_host(h)
        for h in (os.environ.get(_OFFICE_HOSTS_ENV) or "").split(",")
        if h.strip()
    } | set(_OFFICE_HOSTNAMES)
    if host in office_hosts:
        return "office"
    return None
