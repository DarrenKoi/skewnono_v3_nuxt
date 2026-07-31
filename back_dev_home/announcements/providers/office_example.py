"""Tracked office adapter for operator announcements, backed by one Redis key.

Copy to ``office.py`` to activate (``cp office_example.py office.py``) — this
file holds no in-house address or secret, so the copy is verbatim. The Redis
host/password come from ``back_dev_home/.env`` via ``_runtime/office_redis.py``.

    skewnono:announcements   STRING  a JSON array of Announcement rows

WHY REDIS AND NOT THE JSON FILE. The mock reads
``announcements/announcements.json`` from disk, which works at home and is even
multi-worker-safe (it re-reads on mtime change). It is the *operational* story
that fails at the office: in Phase 3 the app lives at
``/project/workSpace/`` on a cloud host, so editing that file means shell access
on the box, and the announcement most worth posting is the one about the box
being unwell. A Redis value can be set from anywhere on the internal network,
takes effect on the next request for every worker, and needs no redeploy.
Publishing a banner becomes, from any office machine:

    redis-cli -h "$REDIS_HOST" -a "$REDIS_PASSWORD" SET skewnono:announcements \\
      '[{"id":"2026-07-30-maint","level":"warning","title":"...","body":"..."}]'

EVERY FAILURE DEGRADES TO "NO BANNERS", NEVER TO AN ERROR. ``routes.py`` is
``jsonify(get_announcements())`` with no try/except, and the SPA calls this
endpoint on every page load — so a raise here is a 500 on every page. A missing
key, an empty value, a truncated paste, a JSON object where an array belongs, a
non-dict row, Redis itself being down, and ``REDIS_*`` not being configured all
resolve to ``[]`` with a warning in the log. The mock's own "missing file is a
normal empty store" rule is the same instinct; this adapter extends it to every
way a hand-edited value can be wrong.

The unconfigured case is the one place this adapter deliberately differs from
``access_control``, which lets a missing ``REDIS_HOST`` become a 503:
enforcement failing loudly is correct, a decorative banner breaking every page
is not. The deviation is expressed by *which client accessor is called* —
:func:`redis_client_or_none` here, ``redis_client`` there — rather than by
catching a bare ``RuntimeError``, so it is visible at the call site and cannot
swallow an unrelated defect from the shared plumbing.

The non-dict-row tolerance is shared, not office-only hardening: both providers
read hand-edited data, so ``mock._load`` applies the same skip to
``announcements.json`` — a bare string row is dropped there too, never an
AttributeError.

NO CACHE, deliberately. The mock caches on file mtime; a Redis GET per page load
is cheap enough that caching would only add a window where an operator has
published a notice and the app is still serving the old one. Announcements are
posted precisely when something is going wrong, so staleness is the expensive
failure.

``is_active`` is imported from ``providers.mock`` rather than restated (it is
public there precisely because this adapter shares it, and it uses that
module's ``_parse_bound`` internally). The active-window semantics — either
bound optional, an unparseable bound treated as absent, and a naive stamp read
as KST so operators can type ``2026-05-07T18:00:00`` without an offset — must
not drift between providers, since the same operator writes both.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from back_dev_home._runtime.office_redis import STORE_ERRORS, redis_client_or_none
from back_dev_home.announcements.contracts import Announcement
from back_dev_home.announcements.providers.mock import is_active

__all__ = ["get_announcements"]

logger = logging.getLogger("skewnono.announcements")

_KEY = "skewnono:announcements"


def _client():
    """The client, or None when Redis is not configured.

    ``redis_client_or_none`` rather than ``redis_client`` is the whole
    expression of this adapter's deviation: enforcement features let a missing
    ``REDIS_HOST`` become a 503, a decorative banner must not break every page.
    Asking as a value beats catching a bare ``RuntimeError``, which would also
    swallow unrelated bugs from the shared plumbing.

    Also the seam the tests patch to inject a fake.
    """
    return redis_client_or_none()


def _load() -> list[Announcement]:
    """Read and parse the announcement array, or return ``[]`` for any problem.

    Deliberately broad: everything reachable from here is operator-edited text,
    and the caller has no error path (see the module docstring).
    """
    client = _client()
    if client is None:
        logger.warning("announcement store not configured; serving no banners")
        return []
    try:
        raw = client.get(_KEY)
    except STORE_ERRORS:
        logger.warning("announcement store unreachable; serving no banners")
        return []
    if not raw:
        return []  # unset key or empty value — a normal "nothing posted" state
    try:
        parsed = json.loads(raw)
    except ValueError:
        logger.warning("announcement value is not valid JSON; serving no banners")
        return []
    if not isinstance(parsed, list):
        logger.warning(
            "announcement value is %s, expected a JSON array; serving no banners",
            type(parsed).__name__,
        )
        return []
    rows = [row for row in parsed if isinstance(row, dict)]
    if len(rows) != len(parsed):
        logger.warning(
            "announcement array had %d non-object row(s); skipping them",
            len(parsed) - len(rows),
        )
    return rows


def get_announcements() -> list[Announcement]:
    """Currently-active announcements, in stored order."""
    now = datetime.now(timezone.utc)
    return [row for row in _load() if is_active(row, now)]
