"""The member directory: a LASTUSER cookie expanded into a person.

The cookie carries an employee number and nothing else. Redis holds the rest in
the ``members`` hash — one document per empno — so a page can greet someone by
name and an admin screen can say which org a request came from.

Three rules shape everything here.

**A directory miss is never an error.** The cookie already identified the
caller; the name is decoration on top of an identity that is complete without
it. Every failure path — no Redis, hash absent, member absent, value
undecodable — returns the same :class:`Member` carrying just the id, so callers
have no "lookup failed" branch to forget. This is deliberately unlike the office
data adapters, which raise so the SPA can show an outage: a directory outage
must not cost anyone access to a page they are entitled to.

**The lookup is not on the request path.** ``identify()`` runs in the app's
first ``before_request``, on every request including each ``_nuxt/`` bundle — a
Redis round trip there would add one HGET per asset on a cold page load. Callers
ask for a profile only when they are about to show one, and answers are cached
per process.

**Home never dials Redis.** Which side we are on is ``get_mode()``, the same
knob the data providers use — not ``is_cloud()``, which cannot tell home from
office-localhost. Home's ``REDIS_HOST`` points at an office host it cannot
reach, so trying costs the full socket timeout per cold lookup and then yields
nothing anyway; home gets a fabricated row instead, which is also the only way
the enriched shape gets exercised before it reaches the cloud.

**empno is trusted from the cookie, not from the document.** The office record
is expected to agree, but if it disagrees the cookie wins: it is what access
control, the admin allowlist and the activity log already keyed on, and letting
a directory row rename the caller mid-request would split one person across two
identities.
"""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from typing import Optional, TypedDict

from .._runtime.data_provider import get_mode
from .._runtime.office_redis import STORE_ERRORS, redis_client_or_none, redis_text

logger = logging.getLogger(__name__)

# HGET members <empno> -> a JSON document with the fields below.
# OFFICE-VERIFY: the hash name and the field spellings are user-confirmed
# (2026-07-31); that the value is JSON rather than another encoding is an
# assumption, which is why a decode failure degrades instead of raising.
MEMBERS_KEY = "members"

# Everything except empno is optional: a member row may be partial, and a
# missing dept is not worth failing a page over.
_PROFILE_FIELDS = ("emp_nm", "dept_nm", "organ_cd", "upper_organ_nm")

# Directory data changes on the order of org reshuffles, not minutes, but a
# uwsgi worker lives for weeks — so cache with an expiry rather than forever.
_TTL_SECONDS = 600


class Member(TypedDict):
    """One person. ``empno`` is always present; the rest may be None."""

    empno: str
    emp_nm: Optional[str]
    dept_nm: Optional[str]
    organ_cd: Optional[str]
    upper_organ_nm: Optional[str]


def bare_member(user_id: str) -> Member:
    """The fallback shape: identified, but nothing known beyond the id.

    Public because it is also the right answer for callers that have an id and
    no reason to hit the directory at all.
    """
    return {
        "empno": user_id,
        "emp_nm": None,
        "dept_nm": None,
        "organ_cd": None,
        "upper_organ_nm": None,
    }


def _coerce(value) -> Optional[str]:
    """Directory values to str-or-None.

    A JSON document can carry a null, a number (organ_cd is plausibly one), or
    an empty string for "not set" — all of which must read as absent or as text
    rather than leaking a non-str into a response the SPA renders.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decode(raw: bytes, user_id: str) -> Member:
    document = json.loads(redis_text(raw))
    if not isinstance(document, dict):
        raise ValueError(f"expected a JSON object, got {type(document).__name__}")
    member = bare_member(user_id)
    for field in _PROFILE_FIELDS:
        member[field] = _coerce(document.get(field))
    return member


def _home_member(user_id: str) -> Member:
    """A fabricated row so home development sees the enriched shape.

    Without this, home has no Redis, every lookup degrades to `bare_member`,
    and the UI gets built against an empno and nothing else — then meets real
    names for the first time on the cloud. The values are deliberately obvious
    placeholders: this mock stands in for the *shape* of a member row, and must
    never imitate office values it cannot know.
    """
    return {
        "empno": user_id,
        "emp_nm": f"홍길동({user_id})",
        "dept_nm": "계측기술팀",
        "organ_cd": "MOCK-ORG",
        "upper_organ_nm": "제조기술",
    }


def _fetch(user_id: str) -> Member:
    # Mode, not is_cloud(). Home has REDIS_HOST set — it points at the office
    # Redis, which is unreachable from here — so "is the client configured"
    # answers yes and then every cold lookup burns the full socket timeout
    # (10s: 5s connect, one retry) before degrading. Worse, it degrades to the
    # bare record, so home never sees the enriched shape it exists to build
    # against. get_mode() is the same knob the data providers use and is the
    # only one that separates home from office-localhost, where REDIS_HOST is
    # set AND reachable.
    if get_mode() != "office":
        return _home_member(user_id)

    client = redis_client_or_none()
    if client is None:
        # Office mode with no REDIS_HOST: an incomplete .env. Worth knowing
        # about, but not worth a 503 — and never worth inventing a name for a
        # real person, so this path stays bare rather than fabricating.
        logger.warning(
            "office mode but Redis is unconfigured; "
            "member names will be missing for every user"
        )
        return bare_member(user_id)

    try:
        raw = client.hget(MEMBERS_KEY, user_id)
    except STORE_ERRORS as exc:
        logger.warning("member directory unreachable for %s: %s", user_id, exc)
        return bare_member(user_id)

    if raw is None:
        # A real, ordinary outcome: contractors and service accounts hold a
        # LASTUSER cookie without a directory row. Not logged — it would be
        # every request from those users, forever.
        return bare_member(user_id)

    try:
        return _decode(raw, user_id)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        # The one case that means our assumption about the value encoding is
        # wrong. Log it loudly enough to find, then degrade like the rest.
        logger.warning(
            "member document for %s is not the expected JSON object (%s: %s); "
            "first bytes %r",
            user_id,
            type(exc).__name__,
            exc,
            raw[:32],
        )
        return bare_member(user_id)


@lru_cache(maxsize=1024)
def _cached(user_id: str, _bucket: int) -> Member:
    """Cache keyed on (user, time bucket) so entries expire without a sweeper.

    The bucket is part of the key rather than a stored timestamp, so an expiry
    is a cache miss on a new key — no eviction pass, no lock, and a stale entry
    can never be served. lru_cache drops the superseded buckets once maxsize is
    reached.
    """
    return _fetch(user_id)


def lookup_member(user_id: Optional[str]) -> Optional[Member]:
    """The person behind a user id, or None if there is no user id.

    Never raises and never returns a half-built record: an unidentified caller
    gets None, and an identified one always gets at least their empno.
    """
    if not user_id:
        return None
    return _cached(user_id, int(time.time() // _TTL_SECONDS))


def reset_cache() -> None:
    """Drop cached profiles. For tests, and for an admin-triggered refresh."""
    _cached.cache_clear()
