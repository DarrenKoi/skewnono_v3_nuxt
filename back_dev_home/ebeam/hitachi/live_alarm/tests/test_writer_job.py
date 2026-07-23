"""The writer's behavioural contract.

The single most important test here is that a failed fetch leaves the
heartbeat alone. Everything about distinguishing "quiet fab" from "we
know nothing" rests on that.
"""

import json

import pytest

from back_dev_home.ebeam.hitachi.live_alarm import board
from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis
from back_dev_home.ebeam.hitachi.live_alarm.writer import job


FABS = [("cd-sem", "R3"), ("cd-sem", "M16A")]


def _row(eqp_id="MXCD101", utc9="1970-01-12 22:46:40"):
    # KST for epoch 1_000_000 — FakeRedis()'s default clock. A calendar-real
    # date here would land ~1.78e9s in the future and get silently dropped
    # by normalize.to_events's FUTURE_TOLERANCE_SEC guard, zeroing out every
    # event these tests mean to write.
    return {
        "EQP_ID": eqp_id, "ALID": "9006", "ALARM_NAME": "Align Fail",
        "UTC9": utc9, "RECIPE_ID": "MONITOR/CD_TOP_01",
        "OPERATION_DESC": "CD MEASUREMENT", "LOT_TYPE_CD": "PROD",
    }


def _meta(client, tool_slug="cd-sem", fab_name="R3"):
    _, meta_key = job.keys(tool_slug, fab_name)
    raw = client.get(meta_key)
    return json.loads(raw.decode()) if raw else None


def _events(client, tool_slug="cd-sem", fab_name="R3"):
    events_key, _ = job.keys(tool_slug, fab_name)
    return client.store_zset(events_key)


def test_a_successful_poll_writes_events_and_meta():
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [_row()], client=client, fabs=FABS)
    assert len(_events(client)) == 1
    assert _meta(client)["polled_at"] == 1_000_000


def test_an_empty_window_still_advances_the_heartbeat():
    # "No alarms" is a successful poll, not a failure. Conflating the two
    # is what makes a quiet fab indistinguishable from a dead feed.
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)
    assert _events(client) == {}
    assert _meta(client)["polled_at"] == 1_000_000


def test_a_failed_fetch_leaves_the_heartbeat_untouched():
    # THE critical test. If a failure stamped the heartbeat, the screen
    # would report a healthy feed while knowing nothing.
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [_row()], client=client, fabs=FABS)
    before = _meta(client)["polled_at"]

    client.advance(300)

    def boom(tool_slug, fab_name, window):
        raise RuntimeError("in-house API down")

    with pytest.raises(RuntimeError):
        job.run_once(fetch=boom, client=client, fabs=FABS)

    assert _meta(client)["polled_at"] == before


def test_one_failing_fab_does_not_block_the_others():
    client = FakeRedis()

    def selective(tool_slug, fab_name, window):
        if fab_name == "R3":
            raise RuntimeError("this fab only")
        return [_row(eqp_id="MXCD204")]

    job.run_once(fetch=selective, client=client, fabs=FABS)

    assert _meta(client, fab_name="R3") is None
    assert _meta(client, fab_name="M16A")["polled_at"] == 1_000_000


def test_a_partial_failure_does_not_raise():
    client = FakeRedis()

    def selective(tool_slug, fab_name, window):
        if fab_name == "R3":
            raise RuntimeError("this fab only")
        return []

    job.run_once(fetch=selective, client=client, fabs=FABS)  # must not raise


def test_total_failure_raises_so_the_host_records_an_error():
    # Otherwise TaskLogger writes an 'end' record and the ops dashboard
    # shows green while every fab is dark.
    client = FakeRedis()

    def boom(tool_slug, fab_name, window):
        raise RuntimeError("all down")

    with pytest.raises(RuntimeError):
        job.run_once(fetch=boom, client=client, fabs=FABS)


def test_running_twice_on_the_same_response_is_idempotent():
    # This is the evidence for "safe on a scheduler with no distributed
    # lock". If it ever fails, that claim is void.
    client = FakeRedis()
    fetch = lambda t, f, w: [_row(), _row(eqp_id="MXCD204")]

    job.run_once(fetch=fetch, client=client, fabs=FABS)
    first = dict(_events(client))
    job.run_once(fetch=fetch, client=client, fabs=FABS)

    assert _events(client) == first


def test_events_past_the_retention_bound_are_pruned():
    client = FakeRedis()
    events_key, _ = job.keys("cd-sem", "R3")
    client.zsets[events_key] = {'{"id":"ancient"}': 1_000_000 - 5_000}

    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)

    assert '{"id":"ancient"}' not in _events(client)


def test_the_fab_is_recorded_in_the_registry():
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)
    assert client.sismember(job.REGISTRY_KEY, "cd-sem:R3")


def test_a_recovery_poll_widens_the_window():
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)
    client.advance(300)

    seen: list[int] = []

    def record(tool_slug, fab_name, window):
        seen.append(window)
        return []

    job.run_once(fetch=record, client=client, fabs=FABS)
    assert all(w > 60 for w in seen)


def test_written_members_are_readable_by_the_reader():
    # The two services share no Python. This is the only thing standing
    # between them and silent schema drift.
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [_row()], client=client, fabs=FABS)

    events_key, _ = job.keys("cd-sem", "R3")
    raw = client.zrangebyscore(events_key, "-inf", "+inf")
    parsed = board.parse_members(raw)

    assert len(parsed) == 1
    assert parsed[0]["kind"] == "align"
    assert parsed[0]["id"] == parsed[0]["eqp_id"] + "|9006|" + parsed[0]["occurred_at"]


def test_prune_below_board_window_is_refused(monkeypatch):
    # The env override that actually takes effect must honour the same
    # invariant contracts.py only asserts for the fixed constant: a prune
    # horizon shorter than the reader's board window silently deletes visible
    # history. run_once refuses rather than corrupt the board.
    monkeypatch.setattr(job, "PRUNE_SEC", job.BOARD_WINDOW_SEC - 1)
    client = FakeRedis()
    with pytest.raises(ValueError):
        job.run_once(fetch=lambda t, f, w: [_row()], client=client, fabs=FABS)
    # And it refuses BEFORE writing anything.
    events_key, meta_key = job.keys("cd-sem", "R3")
    assert client.store_zset(events_key) == {}
    assert client.get(meta_key) is None


def test_prune_at_the_board_window_is_allowed(monkeypatch):
    monkeypatch.setattr(job, "PRUNE_SEC", job.BOARD_WINDOW_SEC)
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)  # must not raise
