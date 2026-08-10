"""The gate that keeps concurrent requests for one image to one tool visit.

The gate only provides mutual exclusion; the DEDUP comes from the caller
re-reading the cache inside it (see test_routes_serve). Both halves are needed
— exclusion alone would serialise the waiters and still send every one of them
to the tool, which is slower AND no lighter.

The same is true of the failure path, and there the re-read cannot help: a
failed fetch caches nothing, so the leader's exception is handed to the waiters
already queued behind it instead.
"""

import threading
import time

import pytest

from back_dev_home.msr_image.single_flight import _attempts, fetch_gate


@pytest.fixture(autouse=True)
def _clean_registry():
    _attempts.clear()
    yield
    _attempts.clear()


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
    assert _attempts == {}


def test_the_entry_lives_exactly_as_long_as_the_attempt():
    """It must be published while the leader is inside — that is what makes a
    concurrent arrival a waiter rather than a second visitor to the tool — and
    gone the moment the leader returns, so the next arrival starts fresh."""
    holder_in = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with fetch_gate("img-a"):
            holder_in.set()
            release.wait(timeout=2.0)

    t = threading.Thread(target=holder)
    t.start()
    holder_in.wait(timeout=2.0)
    assert "img-a" in _attempts
    release.set()
    t.join()
    assert _attempts == {}


def test_the_leaders_failure_is_raised_in_the_waiters():
    """Without this each waiter would find the cache still empty and take its
    own turn at the sick tool — serially, so the k-th waiter waits k fetches."""
    leader_in = threading.Event()
    boom = RuntimeError("tool blew up")
    seen: list[BaseException | None] = []
    seen_guard = threading.Lock()

    def leader() -> None:
        with pytest.raises(RuntimeError):
            with fetch_gate("img-a"):
                leader_in.set()
                time.sleep(0.05)
                raise boom

    def waiter() -> None:
        try:
            with fetch_gate("img-a"):
                pass
        except BaseException as exc:  # noqa: BLE001 - recording, not handling
            with seen_guard:
                seen.append(exc)
        else:
            with seen_guard:
                seen.append(None)

    lead = threading.Thread(target=leader)
    lead.start()
    leader_in.wait(timeout=2.0)
    waiters = [threading.Thread(target=waiter) for _ in range(3)]
    for w in waiters:
        w.start()
    for t in (lead, *waiters):
        t.join()

    # The real object, so the route's per-error status mapping still applies.
    assert seen == [boom, boom, boom]


def test_a_failure_is_not_remembered_for_the_next_arrival():
    """A tool that recovers must not stay broken because we cached its error."""
    with pytest.raises(RuntimeError):
        with fetch_gate("img-a"):
            raise RuntimeError("tool blew up")

    entered = False
    with fetch_gate("img-a"):
        entered = True
    assert entered


def test_an_interrupt_in_the_leader_is_not_shared():
    """A KeyboardInterrupt is about the leader's own thread dying, not about
    the tool, so a waiter must be free to run its body (and re-read the cache)
    rather than inherit it."""
    leader_in = threading.Event()
    ran: list[bool] = []

    def leader() -> None:
        with pytest.raises(KeyboardInterrupt):
            with fetch_gate("img-a"):
                leader_in.set()
                time.sleep(0.05)
                raise KeyboardInterrupt

    def waiter() -> None:
        with fetch_gate("img-a"):
            ran.append(True)

    lead = threading.Thread(target=leader)
    lead.start()
    leader_in.wait(timeout=2.0)
    w = threading.Thread(target=waiter)
    w.start()
    for t in (lead, w):
        t.join()

    assert ran == [True]
