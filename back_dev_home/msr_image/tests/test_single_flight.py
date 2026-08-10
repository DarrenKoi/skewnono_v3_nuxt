"""The gate that keeps concurrent requests for one image to one tool visit.

The gate only provides mutual exclusion; the DEDUP comes from the caller
re-reading the cache inside it (see test_routes_serve). Both halves are needed
— exclusion alone would serialise the waiters and still send every one of them
to the tool, which is slower AND no lighter.
"""

import threading
import time

import pytest

from back_dev_home.msr_image import single_flight
from back_dev_home.msr_image.single_flight import _locks, fetch_gate


@pytest.fixture(autouse=True)
def _clean_registry():
    _locks.clear()
    yield
    _locks.clear()


def test_the_same_key_is_held_by_one_thread_at_a_time():
    order: list[str] = []

    def worker(name: str) -> None:
        with fetch_gate("img-a"):
            order.append(f"{name}-in")
            time.sleep(0.05)
            order.append(f"{name}-out")

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("t1", "t2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Whoever went first, no interleaving: an "in" is always followed by its
    # own "out".
    assert order[0].endswith("-in") and order[1].endswith("-out")
    assert order[2].endswith("-in") and order[3].endswith("-out")


def test_different_keys_do_not_block_each_other():
    """A single global lock would serialise a whole gallery's loading."""
    started = threading.Barrier(2, timeout=2.0)

    def worker(key: str) -> None:
        with fetch_gate(key):
            started.wait()  # times out and raises if the two are serialised

    threads = [threading.Thread(target=worker, args=(k,)) for k in ("img-a", "img-b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not started.broken


def test_an_exception_inside_the_gate_still_releases_it():
    """One tool error must not park a worker thread on that key forever."""
    with pytest.raises(RuntimeError):
        with fetch_gate("img-a"):
            raise RuntimeError("tool blew up")

    # Provable by the next acquisition succeeding without blocking.
    with fetch_gate("img-a"):
        pass


def test_the_registry_does_not_grow():
    """Keys are (msr, filename) pairs — unbounded, so entries must not leak."""
    for i in range(50):
        with fetch_gate(f"img-{i}"):
            pass
    assert _locks == {}


def test_a_waiter_keeps_the_entry_alive_while_it_waits():
    """Dropping the entry while someone still waits would hand the next
    arrival a DIFFERENT lock object, and the exclusion would be lost."""
    holder_in = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with fetch_gate("img-a"):
            holder_in.set()
            release.wait(timeout=2.0)

    t = threading.Thread(target=holder)
    t.start()
    holder_in.wait(timeout=2.0)
    assert "img-a" in _locks
    release.set()
    t.join()
    assert _locks == {}


def test_a_failed_acquire_undoes_the_registry_claim_without_releasing():
    """If lock.acquire() itself raises (e.g. a KeyboardInterrupt delivered
    while blocked), the registry claim made just before it must be undone —
    otherwise the entry, and its count, leak forever and the "last participant
    deletes the entry" invariant breaks. This must NOT be fixed by moving
    acquire() inside the existing try/finally: that finally calls
    lock.release(), which would raise "release unlocked lock" on a lock this
    thread never acquired, masking the original exception."""

    class _BoomError(Exception):
        pass

    class _ExplodingLock:
        def acquire(self) -> None:
            raise _BoomError("acquire blew up")

        def release(self) -> None:
            raise AssertionError("release must not be called: acquire never succeeded")

    single_flight._locks["img-a"] = (_ExplodingLock(), 0)

    with pytest.raises(_BoomError):
        with fetch_gate("img-a"):
            pass  # pragma: no cover - never reached

    assert _locks == {}
