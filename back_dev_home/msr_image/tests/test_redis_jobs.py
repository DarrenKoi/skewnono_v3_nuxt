"""RedisJobRegistry — the office multi-worker job store.

Verified against an injected fake rather than a live server: home has no Redis,
and the point under test is our key layout / TTL discipline, not redis-py.
"""

import json

import pytest

from back_dev_home.msr_image.redis_jobs import RedisJobRegistry


class FakeRedis:
    """In-memory stand-in speaking the byte-oriented dialect of the shared
    office client, which is built with ``decode_responses=False`` (its values
    are normally parquet DataFrames). Returning str here instead of bytes would
    let a decoding bug pass the tests and fail at the office."""

    def __init__(self):
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.lists: dict[str, list[bytes]] = {}
        self.ttls: dict[str, int] = {}

    @staticmethod
    def _b(v) -> bytes:
        return v if isinstance(v, bytes) else str(v).encode()

    def hset(self, key, field=None, value=None, mapping=None):
        h = self.hashes.setdefault(key, {})
        for k, v in (mapping or {}).items():
            h[self._b(k)] = self._b(v)
        if field is not None:
            h[self._b(field)] = self._b(value)

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(self._b(field))

    def hincrby(self, key, field, amount=1):
        h = self.hashes.setdefault(key, {})
        total = int(h.get(self._b(field), b"0")) + amount
        h[self._b(field)] = self._b(total)
        return total

    def rpush(self, key, *values):
        lst = self.lists.setdefault(key, [])
        lst.extend(self._b(v) for v in values)
        return len(lst)

    def lrange(self, key, start, end):
        lst = self.lists.get(key, [])
        return list(lst[start:] if end == -1 else lst[start:end + 1])

    def expire(self, key, seconds):
        if key in self.hashes or key in self.lists:
            self.ttls[key] = seconds
            return True
        return False

    def scan_iter(self, match=None):
        prefix = (match or "*").rstrip("*")  # only trailing-* patterns are used
        for key in list(self.hashes) + list(self.lists):
            if key.startswith(prefix):
                yield key.encode()

    # -- test-only: let every pending TTL elapse, as Redis would in job_ttl s.
    def elapse_ttls(self):
        for key in list(self.ttls):
            self.hashes.pop(key, None)
            self.lists.pop(key, None)
            del self.ttls[key]


@pytest.fixture
def fake():
    return FakeRedis()


@pytest.fixture
def reg(fake):
    return RedisJobRegistry(job_ttl=900, client_factory=lambda: fake)


def test_lifecycle_counts(reg):
    jid = reg.create(total=3)
    st = reg.get(jid)
    assert st["job_id"] == jid
    assert st["status"] == "running" and st["total"] == 3 and st["done"] == 0

    reg.record_ok(jid)
    reg.record_failure(jid, "bad.jpeg", "timeout")
    reg.record_ok(jid)
    reg.finish(jid)

    st = reg.get(jid)
    assert st["status"] == "done"
    assert st["done"] == 3 and st["ok"] == 2 and st["ng"] == 1
    assert st["failures"] == [{"name": "bad.jpeg", "error": "timeout"}]


def test_unknown_job_is_none(reg):
    assert reg.get("nope") is None


def test_set_total_fills_in_an_unknown_total(reg):
    jid = reg.create(total=0)
    assert reg.get(jid)["total"] == 0
    reg.set_total(jid, 7)
    assert reg.get(jid)["total"] == 7


def test_mark_error_sets_error_status(reg):
    jid = reg.create(total=2)
    reg.mark_error(jid)
    assert reg.get(jid)["status"] == "error"


def test_running_count_tracks_active_jobs(reg):
    assert reg.running_count() == 0
    a, b = reg.create(total=1), reg.create(total=1)
    assert reg.running_count() == 2
    reg.finish(a)
    assert reg.running_count() == 1
    reg.mark_error(b)  # errored jobs are not running either
    assert reg.running_count() == 0


def test_create_bounded_refuses_at_cap(reg):
    a = reg.create_bounded(total=1, max_running=1)
    assert a is not None
    assert reg.create_bounded(total=1, max_running=1) is None  # at cap
    reg.finish(a)
    assert reg.create_bounded(total=1, max_running=1) is not None  # freed


def test_failures_key_does_not_masquerade_as_a_job(reg):
    # The failures list must not be picked up by the job scan: counted as a job
    # it would inflate running_count and wedge the max_jobs gate shut.
    jid = reg.create(total=1)
    reg.record_failure(jid, "bad.jpeg", "timeout")
    assert reg.running_count() == 1


def test_state_is_shared_across_registry_instances(fake):
    # The whole reason this class exists: under gunicorn -w N the worker that
    # POSTs a download and the worker that polls it are different processes.
    writer = RedisJobRegistry(job_ttl=900, client_factory=lambda: fake)
    poller = RedisJobRegistry(job_ttl=900, client_factory=lambda: fake)

    jid = writer.create(total=2)
    writer.record_ok(jid)
    writer.finish(jid)

    st = poller.get(jid)
    assert st["status"] == "done" and st["ok"] == 1


def test_every_key_carries_the_job_ttl(reg, fake):
    jid = reg.create(total=1)
    reg.record_failure(jid, "bad.jpeg", "timeout")
    assert set(fake.ttls) == {f"skewnono:msr_image:job:{jid}", f"skewnono:msr_image:fail:{jid}"}
    assert all(ttl == 900 for ttl in fake.ttls.values())


def test_finished_jobs_are_evicted(reg, fake):
    # A finished job keeps a TTL, so completed state drains instead of piling up
    # in Redis forever. Polling an evicted job is an unknown job (404), not a
    # half-populated status.
    jid = reg.create(total=1)
    reg.record_ok(jid)
    reg.finish(jid)
    assert fake.ttls[f"skewnono:msr_image:job:{jid}"] == 900

    fake.elapse_ttls()
    assert reg.get(jid) is None
    assert reg.running_count() == 0


def test_counters_are_stored_as_redis_integers(reg, fake):
    # HINCRBY, not read-modify-write: concurrent worker threads in the bounded
    # download pool increment the same job, and a get/put race would lose ticks.
    jid = reg.create(total=2)
    reg.record_ok(jid)
    reg.record_ok(jid)
    assert fake.hashes[f"skewnono:msr_image:job:{jid}"][b"ok"] == b"2"
    assert json.loads(json.dumps(reg.get(jid)))["ok"] == 2  # JSON-serializable
