"""The primitive that keeps concurrent requests for one image to one tool visit.

The dedup is the HANDOVER: the leader runs the fetch and the waiters take its
result. Turn-taking alone would be no lighter — every waiter would still find
the cache empty and go to the tool — and it would be slower, because each
waiter's cache read would land in front of the next one's.

The same is true of the failure path, and there a cache re-read cannot help at
all: a failed fetch caches nothing, so the leader's exception is handed to the
waiters already queued behind it instead.
"""

import threading
import time

import pytest

from back_dev_home.msr_image.single_flight import _attempts, single_flight


@pytest.fixture(autouse=True)
def _clean_registry():
    _attempts.clear()
    yield
    _attempts.clear()


def test_one_fetch_serves_every_caller_that_asked_at_once():
    calls: list[int] = []
    leader_in = threading.Event()
    release = threading.Event()

    def fetch() -> str:
        calls.append(1)
        leader_in.set()
        release.wait(timeout=2.0)
        return "bytes"

    got: list[str] = []
    got_guard = threading.Lock()

    def caller() -> None:
        value = single_flight("img-a", fetch)
        with got_guard:
            got.append(value)

    lead = threading.Thread(target=caller)
    lead.start()
    leader_in.wait(timeout=2.0)
    waiters = [threading.Thread(target=caller) for _ in range(3)]
    for w in waiters:
        w.start()
    release.set()
    for t in (lead, *waiters):
        t.join()

    assert len(calls) == 1  # one visit to the tool
    assert got == ["bytes"] * 4  # and everybody got its result


def test_the_waiters_are_all_released_at_once():
    """No waiter is gated behind another one's turn.

    This is why the leader hands over its RESULT. Handing over the turn
    instead — a lock passed from waiter to waiter, each re-reading the cache
    before it lets the next one go — put a MinIO round trip in front of every
    later waiter, on top of a fetch that may already have run to
    ftp_host_timeout, under a harakiri only twice that.

    A property test, not a regression test: the handoff version took a
    ``with`` block rather than a callable, so no test written against this
    signature can be run against it.
    """
    leader_in = threading.Event()
    release = threading.Event()
    # Fails if the waiters trickle out instead of leaving together.
    all_out = threading.Barrier(3, timeout=0.5)

    def fetch() -> str:
        leader_in.set()
        release.wait(timeout=2.0)
        return "bytes"

    def waiter() -> None:
        single_flight("img-a", fetch)
        all_out.wait()

    lead = threading.Thread(target=single_flight, args=("img-a", fetch))
    lead.start()
    leader_in.wait(timeout=2.0)
    waiters = [threading.Thread(target=waiter) for _ in range(3)]
    for w in waiters:
        w.start()
    release.set()
    for t in (lead, *waiters):
        t.join()

    assert not all_out.broken


def test_different_keys_do_not_block_each_other():
    """A single global lock would serialise a whole gallery's loading."""
    started = threading.Barrier(2, timeout=2.0)

    def fetch() -> None:
        started.wait()  # times out and raises if the two are serialised

    threads = [
        threading.Thread(target=single_flight, args=(k, fetch))
        for k in ("img-a", "img-b")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not started.broken


def test_an_exception_does_not_wedge_the_key():
    """One tool error must not park every later request on that key."""

    def boom() -> None:
        raise RuntimeError("tool blew up")

    with pytest.raises(RuntimeError):
        single_flight("img-a", boom)

    # Provable by the next call running without blocking.
    assert single_flight("img-a", lambda: "bytes") == "bytes"


def test_the_registry_does_not_grow():
    """Keys are (msr, filename) pairs — unbounded, so entries must not leak."""
    for i in range(50):
        single_flight(f"img-{i}", lambda: None)
    assert _attempts == {}


def test_the_entry_lives_exactly_as_long_as_the_attempt():
    """It must be published while the leader is inside — that is what makes a
    concurrent arrival a waiter rather than a second visitor to the tool — and
    gone the moment the leader returns, so the next arrival starts fresh."""
    holder_in = threading.Event()
    release = threading.Event()

    def fetch() -> None:
        holder_in.set()
        release.wait(timeout=2.0)

    t = threading.Thread(target=single_flight, args=("img-a", fetch))
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

    def fetch() -> None:
        leader_in.set()
        time.sleep(0.05)
        raise boom

    def leader() -> None:
        with pytest.raises(RuntimeError):
            single_flight("img-a", fetch)

    def waiter() -> None:
        try:
            single_flight("img-a", fetch)
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

    def boom() -> None:
        raise RuntimeError("tool blew up")

    with pytest.raises(RuntimeError):
        single_flight("img-a", boom)

    ran: list[bool] = []

    def fetch() -> str:
        ran.append(True)
        return "bytes"

    assert single_flight("img-a", fetch) == "bytes"
    assert ran == [True]


def test_a_leader_that_returns_none_is_still_an_answer():
    """None is a value a fetch may legitimately produce; a waiter must take it
    rather than mistake it for "the leader left nothing" and go to the tool."""
    calls: list[int] = []
    leader_in = threading.Event()
    release = threading.Event()

    def fetch() -> None:
        calls.append(1)
        leader_in.set()
        release.wait(timeout=2.0)

    got: list[object] = []

    def waiter() -> None:
        got.append(single_flight("img-a", fetch))

    lead = threading.Thread(target=single_flight, args=("img-a", fetch))
    lead.start()
    leader_in.wait(timeout=2.0)
    w = threading.Thread(target=waiter)
    w.start()
    release.set()
    for t in (lead, w):
        t.join()

    assert calls == [1]
    assert got == [None]


def test_an_interrupt_in_the_leader_is_not_shared():
    """A KeyboardInterrupt is about the leader's own thread dying, not about
    the tool, so a waiter must run the fetch itself rather than inherit it."""
    leader_in = threading.Event()
    ran: list[bool] = []

    def interrupted() -> None:
        leader_in.set()
        time.sleep(0.05)
        raise KeyboardInterrupt

    def leader() -> None:
        with pytest.raises(KeyboardInterrupt):
            single_flight("img-a", interrupted)

    def waiter() -> None:
        single_flight("img-a", lambda: ran.append(True))

    lead = threading.Thread(target=leader)
    lead.start()
    leader_in.wait(timeout=2.0)
    w = threading.Thread(target=waiter)
    w.start()
    for t in (lead, w):
        t.join()

    assert ran == [True]
