"""Which FTP account reaches which tool.

One fleet is not one account. Hitachi tools share ``hitachi``/``hid``, and the
AMAT tools arriving now do not (user-confirmed 2026-08-28) -- the account
varies by fab and by tool, never by vendor family, so there is no family axis
here. ``SKEWNONO_TOOL_FTP_ACCOUNTS`` names the exceptions and everything else
keeps the fleet pair; the parse lives in ``config._accounts``.

The resolved account rides on the ``HostSpec``, not on the downloader, because
the credential is a property of the HOST: one run can span two accounts, which
neither the downloader's single pair nor the FTP proxy host's single
``FTP_PROXY_FTP_USER`` pair can express.

``account_for`` is PURE over rows, the same shape as ``sem_list/roster.py`` and
``ebeam/live_alarm/roster.py``, and for the same reason that file gives: mock
providers import ``sem_list.providers.mock`` directly while office adapters go
through ``sem_list.data``, so a helper that picked its own source would break
that split. ``ftp_account_lookup`` is the office-side loader that supplies the
rows.
"""

import logging
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from back_dev_home.msr_image.config import ImageConfig


__all__ = ["account_for", "ftp_account_lookup"]

_LOG = logging.getLogger(__name__)

# The roster is re-read at most this often. A plain cache would leave a newly
# installed tool resolving to the fleet account until the next restart -- the
# silent wrong-account login this whole mechanism exists to prevent -- and no
# cache would cost a roster read per thumbnail (see ftp_account_lookup).
_ROSTER_TTL_SECONDS = 300.0
_ROSTER: dict[str, Any] = {}


def account_for(
    rows: Iterable[Mapping[str, Any]],
    accounts: Mapping[str, tuple[str, str]],
    eqp_ip: str,
) -> dict[str, str]:
    """The ``HostSpec`` credential kwargs for one tool. PURE.

    ``{}`` means the downloader's own account already covers this tool, which
    is the answer for every tool no entry names.

    The tool is identified through its ``sem_list`` row, never by parsing the
    id: ``ebeam/_tool_specs.py`` is explicit that an ``eqp_id`` is a lookup key
    and not a description, and the same holds for a ``fab_name``.
    """
    row = next((r for r in rows if r["eqp_ip"] == eqp_ip), None)
    if row is None:
        # Not fatal -- the fleet account may well be right -- but it IS how a
        # wrong-account login would happen silently, so say so.
        _LOG.warning(
            "ftp account: %s is not in sem_list; using the fleet account", eqp_ip
        )
        return {}
    # eqp_id beats fab_name: the tool-level entry is the exception that a
    # fab-level entry is stated as the rule for.
    for key in (row["eqp_id"], row["fab_name"]):
        found = accounts.get(key.strip().upper())
        if found is not None:
            return {"user": found[0], "password": found[1]}
    return {}


def _roster() -> list[Mapping[str, Any]]:
    """The sem_list rows, re-read at most every ``_ROSTER_TTL_SECONDS``.

    A refresh failure serves the previous rows rather than blanking accounts
    that worked a minute ago; the FIRST load raises, because falling back to
    the fleet account for a tool that has its own is precisely the wrong-login
    failure being prevented. Same bargain ``ebeam/_office_search.ttl_cache``
    strikes, restated here so ``msr_image`` need not import the OpenSearch
    module to get it.
    """
    now = time.monotonic()
    if _ROSTER and now - _ROSTER["at"] < _ROSTER_TTL_SECONDS:
        return _ROSTER["rows"]
    # Imported here, not at module scope: this module is imported by office
    # adapters that must not pull the sem_list provider chain at import time.
    from back_dev_home.sem_list.data import get_sem_list

    try:
        rows = get_sem_list()
    except Exception:
        if not _ROSTER:
            raise
        _LOG.exception("sem_list refresh failed; serving the previous roster")
        _ROSTER["at"] = now  # back off a full TTL before retrying
        return _ROSTER["rows"]
    _ROSTER.update(rows=rows, at=now)
    return rows


def ftp_account_lookup(cfg: ImageConfig) -> Callable[[str], dict[str, str]]:
    """``eqp_ip -> HostSpec credential kwargs``, for spreading into a spec.

    An unconfigured fleet costs NOTHING -- with no accounts declared the roster
    is never read at all, which is the state of every deployment until the
    first AMAT tool arrives, and the reason this is a closure rather than a
    plain function: the caller pays for the roster only when it can matter.
    """
    if not cfg.ftp_accounts:
        return lambda _eqp_ip: {}

    accounts = cfg.ftp_accounts
    return lambda eqp_ip: account_for(_roster(), accounts, eqp_ip)
