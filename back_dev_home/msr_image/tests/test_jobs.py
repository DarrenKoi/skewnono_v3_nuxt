import threading

from back_dev_home.msr_image.jobs import MemoryJobRegistry


def test_lifecycle_counts():
    reg = MemoryJobRegistry()
    jid = reg.create(total=3)
    st = reg.get(jid)
    assert st["status"] == "running" and st["total"] == 3 and st["done"] == 0

    reg.record_ok(jid)
    reg.record_failure(jid, "bad.jpeg", "timeout")
    reg.record_ok(jid)
    reg.finish(jid)

    st = reg.get(jid)
    assert st["status"] == "done"
    assert st["done"] == 3 and st["ok"] == 2 and st["ng"] == 1
    assert st["failures"] == [{"name": "bad.jpeg", "error": "timeout"}]


def test_unknown_job_is_none():
    assert MemoryJobRegistry().get("nope") is None


def test_concurrent_increments_are_atomic():
    reg = MemoryJobRegistry()
    jid = reg.create(total=200)

    def worker():
        for _ in range(100):
            reg.record_ok(jid)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert reg.get(jid)["done"] == 200 and reg.get(jid)["ok"] == 200


def test_get_returns_isolated_snapshot():
    reg = MemoryJobRegistry()
    jid = reg.create(total=1)
    reg.record_failure(jid, "a.jpeg", "boom")
    snap = reg.get(jid)
    snap["failures"].append({"name": "x", "error": "y"})
    snap["failures"][0]["error"] = "mutated"
    snap["done"] = 999
    fresh = reg.get(jid)
    assert len(fresh["failures"]) == 1
    assert fresh["failures"][0]["error"] == "boom"
    assert fresh["done"] == 1


def test_running_count_tracks_active_jobs():
    reg = MemoryJobRegistry()
    assert reg.running_count() == 0
    j1 = reg.create(total=1)
    j2 = reg.create(total=1)
    assert reg.running_count() == 2
    reg.finish(j1)
    assert reg.running_count() == 1
    reg.finish(j2)
    assert reg.running_count() == 0


def test_create_bounded_refuses_at_cap_atomically():
    reg = MemoryJobRegistry()
    a = reg.create_bounded(total=1, max_running=1)
    assert a is not None
    assert reg.create_bounded(total=1, max_running=1) is None  # at cap
    reg.finish(a)
    assert reg.create_bounded(total=1, max_running=1) is not None  # freed


def test_mark_error_sets_error_status():
    reg = MemoryJobRegistry()
    j = reg.create(total=2)
    reg.mark_error(j)
    assert reg.get(j)["status"] == "error"
