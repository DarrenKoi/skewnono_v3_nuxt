"""The cache and the lock — the whole reason this feature was redesigned.

Almost every assertion here is about how often the OFFICE is called, not about
what the board contains. The board's content is normalize.py's contract.
"""

from back_dev_home.ebeam.hitachi.live_alarm import refresh
from back_dev_home.ebeam.hitachi.live_alarm.contracts import CACHE_TTL_SEC, LOCK_TTL_SEC
from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis


NOW = 1_000_000_000
FAC = "M16"


class Spy:
    """A fetch that records its calls and can be told to fail."""

    def __init__(self, rows=None, fail=False):
        self.rows = rows if rows is not None else []
        self.fail = fail
        self.calls: list[str] = []

    def __call__(self, fac_id):
        self.calls.append(fac_id)
        if self.fail:
            raise RuntimeError("office alarm API is down")
        return self.rows


def _row(eqp_id="MCD101", utc9="2001-09-09 10:46:40", alid="9006"):
    return {"EQP_ID": eqp_id, "ALID": alid, "UTC9": utc9, "ALARM_NAME": "Align Fail"}


def _fresh(client, spy, now):
    refresh.ensure_fresh(client, FAC, now=now, fetch=spy)


def test_cold_cache_fetches_once():
    client, spy = FakeRedis(), Spy([_row()])
    _fresh(client, spy, NOW)
    assert spy.calls == [FAC]


def test_second_call_inside_the_ttl_does_not_touch_the_office():
    # THE core claim: N viewers, one upstream call.
    client, spy = FakeRedis(), Spy([_row()])
    _fresh(client, spy, NOW)
    for offset in range(1, CACHE_TTL_SEC):
        _fresh(client, spy, NOW + offset)
    assert spy.calls == [FAC]


def test_the_office_is_called_again_once_the_ttl_lapses():
    client, spy = FakeRedis(), Spy([_row()])
    _fresh(client, spy, NOW)
    client.advance(CACHE_TTL_SEC)
    _fresh(client, spy, NOW + CACHE_TTL_SEC)
    assert spy.calls == [FAC, FAC]


def test_a_concurrent_caller_serves_the_old_board_instead_of_fetching():
    # Simulates the lock being held by another request already in flight.
    client, spy = FakeRedis(), Spy([_row()])
    lock_key = refresh.keys(FAC).lock
    client.set(lock_key, "someone-elses-token", nx=True, ex=LOCK_TTL_SEC)
    _fresh(client, spy, NOW)
    assert spy.calls == []


def test_a_failed_fetch_does_not_stamp_the_cache():
    # A fresh timestamp over data that never arrived is the one failure mode
    # this design exists to prevent.
    client, spy = FakeRedis(), Spy(fail=True)
    _fresh(client, spy, NOW)
    assert refresh.read_meta(client, FAC) is None


def test_a_failed_fetch_backs_off_until_the_lock_expires():
    client, spy = FakeRedis(), Spy(fail=True)
    _fresh(client, spy, NOW)
    client.advance(LOCK_TTL_SEC - 1)
    _fresh(client, spy, NOW + LOCK_TTL_SEC - 1)
    assert spy.calls == [FAC], "retried while the office was still failing"
    client.advance(1)
    _fresh(client, spy, NOW + LOCK_TTL_SEC)
    assert spy.calls == [FAC, FAC], "never retried after the backoff lapsed"


def test_a_successful_fetch_releases_the_lock_immediately():
    client, spy = FakeRedis(), Spy([_row()])
    _fresh(client, spy, NOW)
    lock_key = refresh.keys(FAC).lock
    assert client.get(lock_key) is None


def test_a_slow_fetch_does_not_delete_its_successors_lock():
    # The release is compare-and-delete. This drives the real path: the
    # holder's lock expires mid-fetch, a successor takes it, and the original
    # then finishes and releases — which must be a no-op on the new holder.
    client = FakeRedis()
    lock_key = refresh.keys(FAC).lock

    def slow(fac_id):
        client.advance(LOCK_TTL_SEC)                      # our lock lapses
        client.set(lock_key, "successor-token", nx=True, ex=LOCK_TTL_SEC)
        return [_row()]

    refresh.ensure_fresh(client, FAC, now=NOW, fetch=slow)
    assert client.get(lock_key) == b"successor-token"


def test_overlapping_snapshots_accumulate_into_one_deduped_board():
    # The office takes no window argument, so successive snapshots overlap.
    # Re-adding an event already present must be a no-op.
    client = FakeRedis()
    first = Spy([_row(utc9="2001-09-09 10:46:40")])
    second = Spy([_row(utc9="2001-09-09 10:46:40"), _row(eqp_id="MCD102")])
    _fresh(client, first, NOW)
    client.advance(CACHE_TTL_SEC)
    _fresh(client, second, NOW + CACHE_TTL_SEC)
    events_key = refresh.keys(FAC).events
    assert len(client.store_zset(events_key)) == 2


def test_ensure_fresh_returns_the_meta_it_just_wrote():
    # Returned rather than re-read: the caller would otherwise need a second
    # round trip to observe the write this very call made.
    client, spy = FakeRedis(), Spy([_row()])
    assert refresh.ensure_fresh(client, FAC, now=NOW, fetch=spy) == {"fetched_at": NOW}


def test_ensure_fresh_returns_the_existing_meta_on_a_cache_hit():
    client, spy = FakeRedis(), Spy([_row()])
    _fresh(client, spy, NOW)
    assert refresh.ensure_fresh(client, FAC, now=NOW + 1, fetch=spy) == {"fetched_at": NOW}


def test_a_failed_fetch_reports_the_last_good_meta_not_a_fresh_one():
    client = FakeRedis()
    _fresh(client, Spy([_row()]), NOW)
    client.advance(CACHE_TTL_SEC)
    reported = refresh.ensure_fresh(
        client, FAC, now=NOW + CACHE_TTL_SEC, fetch=Spy(fail=True)
    )
    assert reported == {"fetched_at": NOW}, "a failed fetch must not look fresh"


def test_a_quiet_facility_still_stamps_the_cache():
    # An empty result is a SUCCESSFUL poll. Not stamping it would leave the
    # board permanently stale and refetch on every single request.
    client, spy = FakeRedis(), Spy([])
    _fresh(client, spy, NOW)
    assert refresh.read_meta(client, FAC) == {"fetched_at": NOW}
    _fresh(client, spy, NOW + 1)
    assert spy.calls == [FAC]


def test_each_facility_has_its_own_cache_and_lock():
    client, spy = FakeRedis(), Spy([_row()])
    refresh.ensure_fresh(client, "M16", now=NOW, fetch=spy)
    refresh.ensure_fresh(client, "R3", now=NOW, fetch=spy)
    assert spy.calls == ["M16", "R3"]


def test_unreadable_meta_is_treated_as_cold_rather_than_fresh():
    client, spy = FakeRedis(), Spy([_row()])
    meta_key = refresh.keys(FAC).meta
    client.set(meta_key, "{not json")
    _fresh(client, spy, NOW)
    assert spy.calls == [FAC]


def test_sibling_fabs_of_one_facility_share_a_single_upstream_call():
    """The headline claim: M16A/M16B/M16C cost ONE office call between them.

    Each fab resolves to fac_id M16, so the second and third viewers hit a
    warm cache. Keying by fab_name instead would have made this three.
    """
    client, spy = FakeRedis(), Spy([_row()])
    for _ in ("M16A", "M16B", "M16C"):
        refresh.ensure_fresh(client, "M16", now=NOW, fetch=spy)
    assert spy.calls == ["M16"]
