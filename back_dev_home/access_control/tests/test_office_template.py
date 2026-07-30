"""The office access_control adapter — Redis-backed exception + denied store.

Verified against an injected fake rather than a live server: home has no Redis,
and what needs proving is the key layout, the fail-safe/fail-closed split, and
that add/remove raise the exception ``routes.py`` already maps to 503.

Outage behavior is the delicate part, and the governing rule is: **never report
an infrastructure failure as a policy decision.**

* ``is_blocked`` / ``list_exceptions`` / ``list_denied`` PROPAGATE. The app
  factory already maps redis ``ConnectionError``/``TimeoutError`` and bare
  ``RuntimeError`` to a JSON 503, so an outage surfaces truthfully. Returning
  ``False`` would let blocked members in; returning ``True`` would tell a
  legitimately-granted member they are "not allowed to use this service", which
  is a lie that generates a support ticket. Propagating is *also* fail-closed —
  the request is not served either way — so it strictly dominates.
* ``add_exception`` / ``remove_exception`` raise ``StoreUnavailableError``,
  which ``routes.py`` catches for a more specific 503 ("grant NOT saved") than
  the generic handler would give.
* ``record_denied`` swallows. It runs after ``is_blocked`` already returned
  True — so the store was readable a moment ago — and a failure here must not
  convert a correct 403 into a 503.

This deliberately diverges from the mock's fail-safe-to-empty reads, whose
failure mode is a corrupt local JSON file rather than an unreachable server.
"""

from datetime import datetime

import pytest
import redis

from back_dev_home.access_control.providers import mock
from back_dev_home.access_control.providers import office_example as office

EXC_KEY = "skewnono:access_control:exceptions"
DENIED_KEY = "skewnono:access_control:denied"


class FakeRedis:
    """In-memory stand-in speaking the byte-oriented dialect of the shared
    office client (``decode_responses=False`` — its usual values are parquet
    DataFrames). Returning str instead of bytes would let a decoding bug pass
    at home and fail at the office.

    ``fail_on`` makes the named commands raise the way a real outage would, so
    each call site's fail-safe/fail-closed contract can be asserted.
    """

    def __init__(self):
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.zsets: dict[str, dict[bytes, float]] = {}
        self.fail_on: set[str] = set()

    @staticmethod
    def _b(v) -> bytes:
        return v if isinstance(v, bytes) else str(v).encode()

    def _guard(self, name: str) -> None:
        if name in self.fail_on or "*" in self.fail_on:
            raise redis.exceptions.ConnectionError("fake outage")

    # -- hash ---------------------------------------------------------
    def hexists(self, key, field):
        self._guard("hexists")
        return self._b(field) in self.hashes.get(key, {})

    def hgetall(self, key):
        self._guard("hgetall")
        return dict(self.hashes.get(key, {}))

    def hget(self, key, field):
        self._guard("hget")
        return self.hashes.get(key, {}).get(self._b(field))

    def hsetnx(self, key, field, value):
        self._guard("hsetnx")
        h = self.hashes.setdefault(key, {})
        if self._b(field) in h:
            return 0
        h[self._b(field)] = self._b(value)
        return 1

    def hdel(self, key, *fields):
        self._guard("hdel")
        h = self.hashes.get(key, {})
        removed = sum(1 for f in fields if h.pop(self._b(f), None) is not None)
        if not h:
            self.hashes.pop(key, None)  # Redis drops an emptied collection
        return removed

    # -- zset ---------------------------------------------------------
    def zadd(self, key, mapping):
        self._guard("zadd")
        z = self.zsets.setdefault(key, {})
        for member, score in mapping.items():
            z[self._b(member)] = float(score)

    def zrem(self, key, *members):
        self._guard("zrem")
        z = self.zsets.get(key, {})
        removed = sum(1 for m in members if z.pop(self._b(m), None) is not None)
        if not z:
            self.zsets.pop(key, None)
        return removed

    def zrevrange(self, key, start, end, withscores=False):
        self._guard("zrevrange")
        z = self.zsets.get(key, {})
        ordered = sorted(z.items(), key=lambda kv: (-kv[1], kv[0]))
        stop = None if end == -1 else end + 1
        window = ordered[start:stop]
        return window if withscores else [m for m, _ in window]

    def zremrangebyrank(self, key, start, end):
        self._guard("zremrangebyrank")
        z = self.zsets.get(key, {})
        ordered = [m for m, _ in sorted(z.items(), key=lambda kv: (kv[1], kv[0]))]
        stop = None if end == -1 else end + 1
        for member in ordered[start:stop]:
            z.pop(member, None)
        if not z:
            self.zsets.pop(key, None)

    def zcard(self, key):
        self._guard("zcard")
        return len(self.zsets.get(key, {}))


@pytest.fixture
def fake(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(office, "_client", lambda: client)
    return client


# ── is_blocked (runs on EVERY request) ──────────────────────────────────


def test_is_blocked_short_circuits_a_non_x_id_without_reading_redis(
    fake, monkeypatch
):
    def explode():
        raise AssertionError("nearly every id is non-X; must not hit Redis")

    monkeypatch.setattr(office, "_client", explode)
    assert office.is_blocked("2067928") is False


def test_is_blocked_is_true_for_an_x_id_with_no_exception(fake):
    assert office.is_blocked("X123456") is True


def test_is_blocked_is_false_once_an_exception_is_granted(fake):
    office.add_exception("X123456")
    assert office.is_blocked("X123456") is False


def test_is_blocked_normalizes_case_and_whitespace(fake):
    office.add_exception("X123456")
    assert office.is_blocked("  x123456 ") is False


def test_is_blocked_propagates_an_outage_instead_of_reporting_denial(fake):
    """A granted member must never be told "not allowed" because Redis blinked.

    The app factory turns this into 503 backend_unreachable, which is both
    truthful and still fail-closed — the request is not served either way.
    """
    office.add_exception("X123456")
    fake.fail_on = {"hexists"}

    with pytest.raises(redis.exceptions.ConnectionError):
        office.is_blocked("X123456")


def test_is_blocked_propagates_a_missing_redis_host(monkeypatch):
    """Unset config is a deploy mistake, not a policy outcome. Bare
    RuntimeError is what the app factory maps to 503 backend_unavailable."""
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.setattr(
        office,
        "_client",
        lambda: (_ for _ in ()).throw(RuntimeError("REDIS_HOST is not set")),
    )

    with pytest.raises(RuntimeError):
        office.is_blocked("X123456")


# ── list_exceptions ─────────────────────────────────────────────────────


def test_list_exceptions_returns_contract_rows(fake):
    office.add_exception("X123456")

    rows = office.list_exceptions()

    assert len(rows) == 1
    assert set(rows[0]) == {"user_id", "granted_at"}
    assert rows[0]["user_id"] == "X123456"


def test_list_exceptions_is_empty_with_no_grants(fake):
    assert office.list_exceptions() == []


def test_list_exceptions_propagates_rather_than_showing_an_empty_table(fake):
    """An admin shown an empty exception list during an outage may conclude the
    grants were lost and start re-granting. A 503 is the honest answer."""
    office.add_exception("X123456")
    fake.fail_on = {"hgetall"}

    with pytest.raises(redis.exceptions.ConnectionError):
        office.list_exceptions()


# ── add_exception ───────────────────────────────────────────────────────


def test_add_exception_returns_the_granted_row(fake):
    row = office.add_exception("x123456")

    assert row["user_id"] == "X123456"
    assert row["granted_at"].endswith("Z")


def test_add_exception_is_idempotent_and_keeps_the_original_grant_time(fake):
    first = office.add_exception("X123456")
    fake.hashes[EXC_KEY][b"X123456"] = b"2020-01-01T00:00:00Z"

    second = office.add_exception("X123456")

    assert second["granted_at"] == "2020-01-01T00:00:00Z"
    assert first["user_id"] == second["user_id"]


def test_add_exception_rejects_an_empty_id(fake):
    with pytest.raises(ValueError):
        office.add_exception("   ")


def test_add_exception_rejects_an_id_the_rule_would_never_block(fake):
    with pytest.raises(ValueError):
        office.add_exception("2067928")


def test_add_exception_clears_a_pending_denied_attempt(fake):
    office.record_denied("X123456")
    assert office.list_denied()

    office.add_exception("X123456")

    assert office.list_denied() == []


def test_add_exception_raises_store_unavailable_when_redis_is_down(fake):
    fake.fail_on = {"hsetnx"}

    with pytest.raises(mock.StoreUnavailableError):
        office.add_exception("X123456")


# ── remove_exception ────────────────────────────────────────────────────


def test_remove_exception_returns_true_then_false(fake):
    office.add_exception("X123456")

    assert office.remove_exception("X123456") is True
    # Real clients retry; a HDEL on a gone field must read as False, not raise.
    assert office.remove_exception("X123456") is False


def test_remove_exception_normalizes_the_id(fake):
    office.add_exception("X123456")
    assert office.remove_exception(" x123456 ") is True


def test_remove_exception_reblocks_the_member(fake):
    office.add_exception("X123456")
    office.remove_exception("X123456")

    assert office.is_blocked("X123456") is True


def test_remove_exception_raises_store_unavailable_when_redis_is_down(fake):
    fake.fail_on = {"hdel"}

    with pytest.raises(mock.StoreUnavailableError):
        office.remove_exception("X123456")


# ── record_denied / list_denied ─────────────────────────────────────────


def test_record_denied_then_list_denied_returns_the_row(fake):
    office.record_denied("X123456")

    rows = office.list_denied()

    assert len(rows) == 1
    assert set(rows[0]) == {"user_id", "last_denied_at"}
    assert rows[0]["user_id"] == "X123456"


def test_list_denied_is_most_recent_first(fake):
    office.record_denied("X111111")
    office.record_denied("X222222")
    office.record_denied("X333333")
    # Force distinct scores; real calls are seconds apart under load.
    z = fake.zsets[DENIED_KEY]
    z[b"X111111"], z[b"X222222"], z[b"X333333"] = 100.0, 200.0, 300.0

    assert [r["user_id"] for r in office.list_denied()] == [
        "X333333",
        "X222222",
        "X111111",
    ]


def test_a_repeat_denial_updates_in_place_rather_than_duplicating(fake):
    office.record_denied("X123456")
    fake.zsets[DENIED_KEY][b"X123456"] = 100.0

    office.record_denied("X123456")

    rows = office.list_denied()
    assert len(rows) == 1
    assert fake.zsets[DENIED_KEY][b"X123456"] != 100.0


def test_denied_buffer_is_capped_at_fifty(fake):
    for i in range(55):
        office.record_denied(f"X{i:06d}")

    assert len(office.list_denied()) == 50


def test_the_trim_evicts_the_oldest_attempts_not_the_newest(fake):
    # Seeded directly with known scores: record_denied's clock has sub-second
    # resolution, so 55 real calls would leave the eviction order ambiguous.
    fake.zsets[DENIED_KEY] = {
        f"X{i:06d}".encode(): float(i) for i in range(55)
    }

    office.record_denied("X999999")  # any call runs the trim

    ids = [r["user_id"] for r in office.list_denied()]
    assert len(ids) == 50
    assert ids[0] == "X999999"       # newest survives, first
    assert "X000000" not in ids      # oldest evicted
    assert "X000005" not in ids      # 6 evicted: 55 seeded + 1 new - 50 cap
    assert "X000006" in ids          # the first survivor


def test_last_denied_at_matches_the_mocks_timestamp_format(fake):
    """Both providers must emit seconds-precision UTC with a literal Z, or the
    frontend would have to branch on provider to parse it."""
    office.record_denied("X123456")

    stamp = office.list_denied()[0]["last_denied_at"]
    reference = mock._now_iso()

    assert stamp.endswith("Z")
    assert len(stamp) == len(reference)
    assert datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is not None


def test_record_denied_never_raises_when_redis_is_down(fake):
    """It runs on the deny path just before a 403 is returned; a raise here
    would turn every blocked request into a 500."""
    fake.fail_on = {"zadd"}

    office.record_denied("X123456")  # must not raise


def test_list_denied_propagates_an_outage(fake):
    office.record_denied("X123456")
    fake.fail_on = {"zrevrange"}

    with pytest.raises(redis.exceptions.ConnectionError):
        office.list_denied()


def test_record_denied_ignores_a_blank_id(fake):
    office.record_denied("   ")
    assert office.list_denied() == []


# ── error-type identity ─────────────────────────────────────────────────


def test_store_unavailable_error_is_the_class_routes_already_catches(fake):
    """routes.py imports StoreUnavailableError from data.py, which re-exports
    the MOCK's class unswitched. A redefined class here would sail past
    `except StoreUnavailableError` and 500 instead of 503."""
    assert office.StoreUnavailableError is mock.StoreUnavailableError


def test_store_unavailable_error_is_not_swallowed_by_the_generic_handler(fake):
    """StoreUnavailableError subclasses RuntimeError, and the app factory's
    RuntimeError handler deliberately rejects subclasses
    (`type(err) is not RuntimeError` → 500). That is fine only because
    routes.py catches it first — so the class must stay a RuntimeError subclass
    AND stay the one routes.py imports."""
    assert issubclass(mock.StoreUnavailableError, RuntimeError)
    assert type(mock.StoreUnavailableError("x")) is not RuntimeError
