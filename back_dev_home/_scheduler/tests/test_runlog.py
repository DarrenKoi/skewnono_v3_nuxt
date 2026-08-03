import pytest

import json
from zoneinfo import ZoneInfo

from back_dev_home._scheduler.runlog import MemoryRunLog, RedisRunLog, kst_stamp


def test_records_are_newest_first():
    log = MemoryRunLog(max_records=10)
    log.record("job_a", "start")
    log.record("job_b", "start")
    rows = log.read(limit=10)
    assert [r["job"] for r in rows] == ["job_b", "job_a"]


def test_ring_buffer_drops_the_oldest():
    log = MemoryRunLog(max_records=2)
    for name in ("a", "b", "c"):
        log.record(name, "start")
    rows = log.read(limit=10)
    assert [r["job"] for r in rows] == ["c", "b"]


def test_every_record_has_ts_job_event():
    log = MemoryRunLog(max_records=5)
    log.record("job_a", "skip", holder="host:123")
    row = log.read(limit=1)[0]
    assert row["job"] == "job_a"
    assert row["event"] == "skip"
    assert row["holder"] == "host:123"
    assert row["ts"].endswith("+09:00")


def test_wrap_brackets_a_successful_call_with_start_and_end():
    log = MemoryRunLog(max_records=10)
    wrapped = log.wrap(lambda: 7, "job_a")
    assert wrapped() == 7
    events = [r["event"] for r in log.read(limit=10)]
    assert events == ["end", "start"]
    assert log.read(limit=10)[0]["duration_ms"] >= 0


def test_wrap_records_error_and_reraises():
    log = MemoryRunLog(max_records=10)

    def boom():
        raise ValueError("nope")

    wrapped = log.wrap(boom, "job_a")
    with pytest.raises(ValueError):
        wrapped()
    rows = log.read(limit=10)
    assert [r["event"] for r in rows] == ["error", "start"]
    assert "nope" in rows[0]["error"]


def test_wrap_uses_the_registry_name_not_the_function_name():
    # The registry key is the job's identity everywhere -- lock key, scheduler
    # job id, and log records. Deriving it from fn.__name__ splits that the
    # moment an entry is named differently from its function.
    log = MemoryRunLog(max_records=10)
    log.wrap(lambda: None, "registry_name")()
    assert log.read(limit=1)[0]["job"] == "registry_name"


def test_kst_stamp_is_second_precision_aware_kst():
    stamp = kst_stamp()
    assert stamp.endswith("+09:00")
    assert "." not in stamp


def test_record_ts_matches_the_scheduler_timezone():
    """``ts`` has to share an offset with the ``scheduled`` field beside it.

    A "missed" record carries APScheduler's ``scheduled_run_time``, which is
    tagged with ``cfg.timezone``. If ``ts`` drifts back to UTC, the two fields
    an operator would naturally compare sit nine hours apart in one record.
    """
    from datetime import datetime

    from back_dev_home._scheduler.config import load_scheduler_config

    log = MemoryRunLog(max_records=5)
    log.record("job_a", "missed")
    ts_offset = datetime.fromisoformat(log.read(limit=1)[0]["ts"]).utcoffset()

    scheduled = datetime.now(ZoneInfo(load_scheduler_config().timezone))
    assert ts_offset == scheduled.utcoffset()


# ── RedisRunLog ─────────────────────────────────────────────────────────────
# The office backend is unreachable from home, so a hand-rolled fake client is
# the only way this path gets exercised before it runs for real. Same shape as
# FakeLock in test_locks.py -- no new dependency.


class FakeRedis:
    """Enough of redis.Redis for LPUSH/LTRIM/LRANGE through a pipeline."""

    def __init__(self, *, fail_on: str | None = None):
        self.items: list[str] = []
        self.calls: list[tuple] = []
        self.fail_on = fail_on

    # -- pipeline ---------------------------------------------------------
    def pipeline(self):
        return _FakePipeline(self)

    # -- direct commands --------------------------------------------------
    def lrange(self, key, start, end):
        if self.fail_on == "lrange":
            raise RuntimeError("redis is down")
        self.calls.append(("lrange", key, start, end))
        return self.items[start : (None if end == -1 else end + 1)]


class _FakePipeline:
    def __init__(self, client: FakeRedis):
        self.client = client
        self.queued: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def lpush(self, key, value):
        self.queued.append(("lpush", key, value))

    def ltrim(self, key, start, end):
        self.queued.append(("ltrim", key, start, end))

    def execute(self):
        if self.client.fail_on == "execute":
            raise RuntimeError("redis is down")
        for call in self.queued:
            self.client.calls.append(call)
            if call[0] == "lpush":
                self.client.items.insert(0, call[2])
            else:
                _, _key, start, end = call
                self.client.items = self.client.items[start : end + 1]
        self.queued = []


def test_record_lpushes_then_ltrims_in_that_order():
    client = FakeRedis()
    log = RedisRunLog(client, "logs", max_records=3)
    log.record("job_a", "start")
    assert [c[0] for c in client.calls] == ["lpush", "ltrim"]
    # LTRIM keeps indices 0..max_records-1, i.e. max_records entries. Using
    # max_records here instead would keep one too many, forever.
    assert client.calls[1] == ("ltrim", "logs", 0, 2)
    assert json.loads(client.items[0])["job"] == "job_a"


def test_ltrim_bounds_the_list_at_max_records():
    client = FakeRedis()
    log = RedisRunLog(client, "logs", max_records=2)
    for name in ("a", "b", "c"):
        log.record(name, "start")
    assert len(client.items) == 2
    assert [json.loads(i)["job"] for i in client.items] == ["c", "b"]


def test_read_returns_newest_first():
    client = FakeRedis()
    log = RedisRunLog(client, "logs", max_records=10)
    log.record("job_a", "start")
    log.record("job_b", "start")
    assert [r["job"] for r in log.read(10)] == ["job_b", "job_a"]


def test_read_skips_a_malformed_entry_instead_of_dying():
    client = FakeRedis()
    log = RedisRunLog(client, "logs", max_records=10)
    log.record("job_a", "start")
    client.items.insert(0, "{not json")
    rows = log.read(10)
    assert [r["job"] for r in rows] == ["job_a"]


def test_record_swallows_a_redis_failure(caplog):
    client = FakeRedis(fail_on="execute")
    log = RedisRunLog(client, "logs", max_records=10)
    with caplog.at_level("ERROR", logger="skewnono.scheduler"):
        log.record("job_a", "start")  # must not raise
    assert "failed to push task-run record" in caplog.text


def test_read_swallows_a_redis_failure_and_returns_empty(caplog):
    client = FakeRedis(fail_on="lrange")
    log = RedisRunLog(client, "logs", max_records=10)
    with caplog.at_level("ERROR", logger="skewnono.scheduler"):
        assert log.read(10) == []
    assert "failed to read task-run records" in caplog.text


def test_wrap_records_start_and_end_through_redis():
    client = FakeRedis()
    log = RedisRunLog(client, "logs", max_records=10)
    log.wrap(lambda: 7, "job_a")()
    assert [r["event"] for r in log.read(10)] == ["end", "start"]
