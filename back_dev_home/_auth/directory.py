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
from collections.abc import Iterable
from functools import lru_cache
from typing import Literal, NamedTuple, Optional, TypedDict

from .._runtime.data_provider import get_mode
from .._runtime.office_redis import STORE_ERRORS, redis_client_or_none, redis_text

logger = logging.getLogger(__name__)

# HGET members <empno> -> a UTF-8 JSON document with the fields below.
# (HMGET for the bulk read; same hash, same document shape.)
# user-confirmed 2026-07-31, whole read path: the office does
# `json.loads(redis.hget("members", str(LASTUSER)).decode("utf-8"))`.
# The decode still degrades rather than raising — not because the encoding is
# in doubt now, but because a single malformed row must not lock a user out.
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


# What the directory was able to say. A closed vocabulary, typed rather than
# left as a commented `str` — the same way `_logging/policy.py` types its
# activity kinds — because `verify.decide` branches on these three values and a
# typo would silently take the accept-everything path.
ProbeStatus = Literal["found", "absent", "unavailable"]


class Probe(NamedTuple):
    """What the directory could tell us about one employee number.

    ``lookup_member`` collapses every failure into the same bare record, which
    is right for display — a directory miss must never cost anyone a page. But
    verification has to tell a *missing row* (this person is not in the
    directory) from an *unreachable directory* (we cannot say), because those
    deserve opposite treatment: one is a fact about the user, the other is a
    fact about us.

    ``member`` is populated only when ``status`` is ``"found"``.
    """

    member: Optional[Member]
    status: ProbeStatus


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


def _fetch(user_id: str) -> Probe:
    # Mode, not is_cloud(). Home has REDIS_HOST set — it points at the office
    # Redis, which is unreachable from here — so "is the client configured"
    # answers yes and then every cold lookup burns the full socket timeout
    # (10s: 5s connect, one retry) before degrading. get_mode() is the same
    # knob the data providers use and is the only one that separates home from
    # office-localhost, where REDIS_HOST is set AND reachable.
    #
    # Home reports "unavailable" rather than the fabricated row: it can display
    # a stand-in name (see `lookup_member`) but it cannot confirm one, and
    # calling it "found" would make every home declaration verify against
    # `홍길동(<사번>)`.
    if get_mode() != "office":
        return Probe(None, "unavailable")

    client = redis_client_or_none()
    if client is None:
        # Office mode with no REDIS_HOST: an incomplete .env. Worth knowing
        # about, but not worth a 503 — and never worth inventing a name for a
        # real person, so this path stays empty rather than fabricating.
        logger.warning(
            "office mode but Redis is unconfigured; "
            "member names will be missing for every user"
        )
        return Probe(None, "unavailable")

    try:
        raw = client.hget(MEMBERS_KEY, user_id)
    except STORE_ERRORS as exc:
        logger.warning("member directory unreachable for %s: %s", user_id, exc)
        return Probe(None, "unavailable")

    if raw is None:
        # A real, ordinary outcome: contractors and service accounts hold a
        # LASTUSER cookie without a directory row. Not logged — it would be
        # every request from those users, forever.
        return Probe(None, "absent")

    try:
        return Probe(_decode(raw, user_id), "found")
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        # The one case that means our assumption about the value encoding is
        # wrong. Log it loudly enough to find, then degrade like an outage —
        # never like a missing row, which would blame the user for our bug.
        logger.warning(
            "member document for %s is not the expected JSON object (%s: %s); "
            "first bytes %r",
            user_id,
            type(exc).__name__,
            exc,
            raw[:32],
        )
        return Probe(None, "unavailable")


@lru_cache(maxsize=1024)
def _cached(user_id: str, _bucket: int) -> Probe:
    """Cache keyed on (user, time bucket) so entries expire without a sweeper.

    The bucket is part of the key rather than a stored timestamp, so an expiry
    is a cache miss on a new key — no eviction pass, no lock, and a stale entry
    can never be served. lru_cache drops the superseded buckets once maxsize is
    reached.
    """
    return _fetch(user_id)


def probe_member(user_id: str) -> Probe:
    """What the directory knows about ``user_id``, failures kept distinct.

    Only verification should call this. Anything that merely displays a name
    wants ``lookup_member``, which cannot leave a caller with a failure branch
    to forget.
    """
    return _cached(user_id, int(time.time() // _TTL_SECONDS))


def lookup_member(user_id: Optional[str]) -> Optional[Member]:
    """The person behind a user id, or None if there is no user id.

    Never raises and never returns a half-built record: an unidentified caller
    gets None, and an identified one always gets at least their empno. This is
    the forgiving face of ``probe_member`` — every failure it distinguishes
    collapses to the same bare record here, so no caller has a "lookup failed"
    branch to forget.
    """
    if not user_id:
        return None
    # Home gets a fabricated row so the enriched shape is exercised before it
    # meets the cloud. The probe reports "unavailable" for the same case,
    # because a row we invented cannot vouch for anybody — display and
    # verification want opposite answers here, which is the whole reason these
    # are two functions.
    if get_mode() != "office":
        return _home_member(user_id)
    return probe_member(user_id).member or bare_member(user_id)


def lookup_members(user_ids: Iterable[str]) -> dict[str, Member]:
    """Profiles for many employee numbers, keyed by id.

    For screens that list people rather than greet one — the admin activity
    table asks for every user it is about to render. Doing that with
    ``lookup_member`` in a loop would be one HGET per row and one socket
    round trip per row; ``HMGET`` asks the same question once.

    Deliberately *not* cached, unlike ``probe_member``. The per-user cache
    exists because ``/api/me`` runs on every page load; this runs when an admin
    opens one screen, so a cache would mostly hold entries nobody reads again
    and would make the table show names that an org reshuffle already changed.
    The single round trip is what makes that affordable.

    Never raises, for the same reason ``lookup_member`` never does: a directory
    outage must cost the names and not the page. Every id asked for is present
    in the result, carrying at least its empno.
    """
    # Dedupe but keep the caller's order, so the HMGET fields line up with the
    # ids we zip them back against.
    wanted = list(dict.fromkeys(uid for uid in user_ids if uid))
    if not wanted:
        return {}

    if get_mode() != "office":
        return {uid: _home_member(uid) for uid in wanted}

    members = {uid: bare_member(uid) for uid in wanted}

    client = redis_client_or_none()
    if client is None:
        logger.warning(
            "office mode but Redis is unconfigured; "
            "member names will be missing for every listed user"
        )
        return members

    try:
        raw_values = client.hmget(MEMBERS_KEY, wanted)
    except STORE_ERRORS as exc:
        logger.warning("member directory unreachable for %d users: %s", len(wanted), exc)
        return members

    for user_id, raw in zip(wanted, raw_values):
        if raw is None:
            # No directory row — ordinary for contractors and service accounts.
            continue
        try:
            members[user_id] = _decode(raw, user_id)
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            # One malformed document must not cost the whole table its names.
            logger.warning(
                "member document for %s is not the expected JSON object (%s: %s)",
                user_id,
                type(exc).__name__,
                exc,
            )
    return members


def reset_cache() -> None:
    """Drop cached profiles. For tests, and for an admin-triggered refresh."""
    _cached.cache_clear()
