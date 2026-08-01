import json
import time

from back_dev_home._scheduler.config import load_scheduler_config
from back_dev_home._scheduler.locks import (
    _redis_lock,
    lock_owner_token,
    make_job_lock,
)


class FakeLock:
    """Enough of redis.lock.Lock for the wrapper's contract."""

    def __init__(self, *, acquirable: bool = True):
        self.acquirable = acquirable
        self.released = False
        self.extends: list[tuple[int, bool]] = []
        self.name = "fake"

    def acquire(self, blocking=False, token=None):
        self.token = token
        return self.acquirable

    def extend(self, ttl, replace_ttl=False):
        self.extends.append((ttl, replace_ttl))

    def release(self):
        self.released = True


def test_home_lock_is_a_passthrough(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    cfg = load_scheduler_config({})
    calls = []
    wrapped = make_job_lock(cfg, "job_a")(lambda: calls.append(1))
    wrapped()
    wrapped()
    assert len(calls) == 2


def test_lock_runs_the_function_and_releases():
    lock = FakeLock(acquirable=True)
    calls = []
    wrapped = _redis_lock(lock, ttl=600, on_skip=None)(lambda: calls.append(1))
    assert wrapped() is None or True
    assert len(calls) == 1
    assert lock.released is True


def test_lock_skips_when_held_and_does_not_call_the_function():
    lock = FakeLock(acquirable=False)
    calls = []
    skips = []
    wrapped = _redis_lock(lock, ttl=600, on_skip=skips.append)(lambda: calls.append(1))
    wrapped()
    assert calls == []
    assert len(skips) == 1


def test_release_still_happens_when_the_function_raises():
    lock = FakeLock(acquirable=True)

    def boom():
        raise ValueError("nope")

    wrapped = _redis_lock(lock, ttl=600, on_skip=None)(boom)
    try:
        wrapped()
    except ValueError:
        pass
    assert lock.released is True


def test_release_error_does_not_replace_the_functions_exception():
    from redis.exceptions import RedisError

    class ExplodingRelease(FakeLock):
        def release(self):
            raise RedisError("connection lost")

    lock = ExplodingRelease(acquirable=True)

    def boom():
        raise ValueError("the real error")

    wrapped = _redis_lock(lock, ttl=600, on_skip=None)(boom)
    try:
        wrapped()
    except Exception as exc:
        # The job's own error must survive; a failed release must not mask it.
        assert isinstance(exc, ValueError)
        assert str(exc) == "the real error"
    else:
        raise AssertionError("expected the function's ValueError")


def test_owner_token_carries_host_and_pid():
    payload = json.loads(lock_owner_token())
    assert set(payload) == {"token", "host", "pid", "acquired"}
    assert isinstance(payload["pid"], int)


def test_renewal_re_arms_the_ttl_with_replace_ttl():
    # Without replace_ttl=True, extend ADDS to the remaining TTL, so every tick
    # pushes expiry further out and a killed process orphans the lock far
    # beyond ttl -- inverting the property the TTL exists to provide.
    #
    # ttl=3 makes the watchdog tick every ttl//3 = 1s, so a job that runs ~1.3s
    # sees at least one renewal. Asserting `extends` is non-empty is the point:
    # without it this test passes vacuously on an empty list, proving nothing.
    lock = FakeLock(acquirable=True)

    wrapped = _redis_lock(lock, ttl=3, on_skip=None)(lambda: time.sleep(1.3))
    wrapped()

    assert lock.extends, "the watchdog never renewed the lock"
    assert all(replace is True for _ttl, replace in lock.extends)
    assert all(ttl == 3 for ttl, _replace in lock.extends)


def test_renewal_stops_when_the_job_finishes():
    # The watchdog must not re-arm a key the wrapper is about to delete.
    lock = FakeLock(acquirable=True)
    wrapped = _redis_lock(lock, ttl=3, on_skip=None)(lambda: None)
    wrapped()
    ticks_at_exit = len(lock.extends)
    time.sleep(1.5)
    assert len(lock.extends) == ticks_at_exit
