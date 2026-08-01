import pytest

from back_dev_home._scheduler.runlog import MemoryRunLog, utc_stamp


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
    assert row["ts"].endswith("+00:00")


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


def test_utc_stamp_is_second_precision_aware_utc():
    stamp = utc_stamp()
    assert stamp.endswith("+00:00")
    assert "." not in stamp
