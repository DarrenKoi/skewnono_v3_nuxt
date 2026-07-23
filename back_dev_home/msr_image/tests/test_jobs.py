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
