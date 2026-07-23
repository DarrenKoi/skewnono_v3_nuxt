import threading

from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.jobs import MemoryJobRegistry, default_registry, make_registry


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


def test_set_total_fills_in_an_unknown_total():
    # The job is minted before the (slow) listing finishes, so it starts with an
    # unknown total of 0 and the worker fills the real count in afterwards.
    reg = MemoryJobRegistry()
    j = reg.create(total=0)
    assert reg.get(j)["total"] == 0
    reg.set_total(j, 7)
    assert reg.get(j)["total"] == 7


def test_set_total_ignores_unknown_job():
    # Same no-op-on-missing contract as the other mutators: a job that expired
    # mid-download must not resurrect or explode in the worker thread.
    MemoryJobRegistry().set_total("nope", 3)


# ── Registry selection ───────────────────────────────────────────────────────
# Shared job state is only needed where requests can land on different
# processes. Home is one process, so it stays on memory and needs no Redis.


def test_make_registry_home_is_the_process_memory_singleton(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    reg = make_registry(load_config({}), provider="mock")
    # Same object as default_registry(): the POST handler, the worker thread and
    # the poll handler must all observe one dict.
    assert reg is default_registry()


def test_make_registry_office_without_redis_stays_memory(monkeypatch):
    # Readiness is two questions. An office adapter alone doesn't imply a
    # multi-worker deploy, and inventing a Redis dependency would break a
    # single-worker office run that has none configured.
    monkeypatch.delenv("REDIS_HOST", raising=False)
    assert make_registry(load_config({}), provider="office") is default_registry()


def test_make_registry_office_with_redis_is_redis_backed(monkeypatch):
    from back_dev_home.msr_image.redis_jobs import RedisJobRegistry

    monkeypatch.setenv("REDIS_HOST", "redis.invalid")
    cfg = load_config({"SKEWNONO_MSR_IMAGE_JOB_TTL": "900"})
    reg = make_registry(cfg, provider="office")
    assert isinstance(reg, RedisJobRegistry)
    assert reg.job_ttl == 900  # SKEWNONO_MSR_IMAGE_JOB_TTL drives key expiry


def test_selecting_the_redis_registry_does_not_connect(monkeypatch):
    # Construction must stay lazy (same contract as MinioImageCache): an
    # unreachable host may not blow up until something is actually stored.
    monkeypatch.setenv("REDIS_HOST", "redis.invalid")
    make_registry(load_config({}), provider="office")
