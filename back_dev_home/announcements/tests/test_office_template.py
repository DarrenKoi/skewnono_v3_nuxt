"""The office announcements adapter — one Redis key holding a JSON array.

Verified against an injected fake rather than a live server. What needs proving
is that a hand-edited value can never 500 the endpoint, and that the active-
window rules (including the KST-naive convention) behave identically to the
mock's — the frontend renders this banner on every page, so a bad edit
degrading to "no banners" is the only acceptable failure mode.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
import redis

from back_dev_home.announcements.providers import office_example as office

KEY = "skewnono:announcements"

ROW = {
    "id": "2026-07-30-notice",
    "level": "info",
    "title": "정기 점검 안내",
    "body": "07-31 02:00~04:00 사이 조회가 지연될 수 있습니다.",
    "dismissible": True,
}


class FakeRedis:
    """Byte-oriented stand-in for the shared office client, which runs
    ``decode_responses=False``."""

    def __init__(self):
        self.strings: dict[str, bytes] = {}
        self.fail = False

    def get(self, key):
        if self.fail:
            raise redis.exceptions.ConnectionError("fake outage")
        return self.strings.get(key)

    def put_json(self, key, value):
        self.strings[key] = json.dumps(value, ensure_ascii=False).encode()


@pytest.fixture
def fake(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(office, "_client", lambda: client)
    return client


def _naive(offset: timedelta) -> str:
    """A wall-clock stamp with no offset, the way an operator would type it."""
    return (datetime.now(timezone.utc) + offset).strftime("%Y-%m-%dT%H:%M:%S")


def _aware(offset: timedelta) -> str:
    return (datetime.now(timezone.utc) + offset).isoformat(timespec="seconds")


# ── happy path ──────────────────────────────────────────────────────────


def test_a_bound_less_row_is_returned_unreshaped_and_active(fake):
    """Equality against the whole row is the wire contract: nothing renamed,
    nothing reshaped, and a row with no starts_at/ends_at is always active."""
    fake.put_json(KEY, [ROW])

    assert office.get_announcements() == [ROW]


def test_order_is_preserved_not_sorted(fake):
    rows = [dict(ROW, id="first"), dict(ROW, id="second"), dict(ROW, id="third")]
    fake.put_json(KEY, rows)

    assert [r["id"] for r in office.get_announcements()] == [
        "first",
        "second",
        "third",
    ]


def test_an_empty_array_is_a_valid_empty_response(fake):
    fake.put_json(KEY, [])
    assert office.get_announcements() == []


# ── active window ───────────────────────────────────────────────────────


def test_a_not_yet_started_announcement_is_hidden(fake):
    fake.put_json(KEY, [dict(ROW, starts_at=_aware(timedelta(days=1)))])
    assert office.get_announcements() == []


def test_an_expired_announcement_is_hidden(fake):
    fake.put_json(KEY, [dict(ROW, ends_at=_aware(timedelta(days=-1)))])
    assert office.get_announcements() == []


def test_an_announcement_inside_its_window_is_shown(fake):
    fake.put_json(
        KEY,
        [
            dict(
                ROW,
                starts_at=_aware(timedelta(days=-1)),
                ends_at=_aware(timedelta(days=1)),
            )
        ],
    )
    assert len(office.get_announcements()) == 1


def test_a_naive_timestamp_is_read_as_kst_not_utc(fake):
    """The operator convention: a stamp with no offset means KST (UTC+9).

    This bound is 4h ahead on the wall clock. Read as KST it resolves to 5h
    *ago* in absolute terms, so the announcement is already active; read as UTC
    it would still be 4h in the future and wrongly hidden. Only the KST reading
    returns a row, which is what makes this a real test of the convention.
    """
    fake.put_json(KEY, [dict(ROW, starts_at=_naive(timedelta(hours=4)))])

    assert len(office.get_announcements()) == 1


def test_an_unparseable_bound_is_treated_as_absent_not_as_expired(fake):
    fake.put_json(KEY, [dict(ROW, starts_at="tomorrow-ish", ends_at="")])
    assert len(office.get_announcements()) == 1


# ── degradation: a hand-edited value must never 500 the page ────────────


def test_a_missing_key_is_an_empty_response_not_an_error(fake):
    assert office.get_announcements() == []


def test_malformed_json_degrades_to_no_banners(fake):
    """routes.py has no try/except and every page hits this endpoint, so a
    truncated paste must not take the whole SPA down."""
    fake.strings[KEY] = b'[{"id": "broken", '

    assert office.get_announcements() == []


def test_a_json_object_instead_of_an_array_degrades_to_no_banners(fake):
    fake.put_json(KEY, {"announcements": [ROW]})
    assert office.get_announcements() == []


def test_a_non_dict_row_is_skipped_rather_than_crashing(fake):
    """Hardening the mock does not have: it calls ``a.get(...)`` straight on
    each row, so a bare string in the array raises AttributeError and 500s."""
    fake.put_json(KEY, ["oops", ROW])

    assert office.get_announcements() == [ROW]


def test_redis_being_down_degrades_to_no_banners(fake):
    fake.fail = True
    assert office.get_announcements() == []


def test_missing_redis_config_degrades_to_no_banners(monkeypatch):
    """Unlike access_control, which lets this become a 503, a decorative banner
    must never break every page in the SPA. Expressed as redis_client_or_none
    returning None rather than as a caught RuntimeError."""
    monkeypatch.setattr(office, "_client", lambda: None)

    assert office.get_announcements() == []


def test_a_real_bug_in_the_store_read_is_not_swallowed(monkeypatch):
    """Only STORE_ERRORS degrade. A defect that is not an outage still surfaces
    instead of silently blanking the banner."""

    class Exploding:
        def get(self, key):
            raise RuntimeError("a real bug, not a config problem")

    monkeypatch.setattr(office, "_client", lambda: Exploding())

    with pytest.raises(RuntimeError):
        office.get_announcements()


def test_an_empty_value_degrades_to_no_banners(fake):
    fake.strings[KEY] = b""
    assert office.get_announcements() == []


# ── no caching ──────────────────────────────────────────────────────────


def test_an_edit_takes_effect_on_the_next_call(fake):
    """Unlike the mock there is no mtime cache, so an operator's edit is live
    immediately for every worker — one Redis GET per page load is cheap."""
    fake.put_json(KEY, [ROW])
    assert len(office.get_announcements()) == 1

    fake.put_json(KEY, [])
    assert office.get_announcements() == []
