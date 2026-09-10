"""Keep concurrent requests for ONE image to one visit to the tool.

The measuring tool's FTP server caps concurrent sessions and engineers use
their own tools against the same equipment, so a session slot is a shared,
scarce resource. Two things make us hold more of them than we need: the
browser re-requests a slow image at 2.5s and 5s (utils/imageRetry.ts), and two
people can open the same MSR at once. Both arrive as concurrent requests for
the SAME cache key, and each used to open its own session.

So the first arrival for a key runs the fetch and everyone who arrives while
it runs gets ITS result — not a turn of their own:

    fetched = single_flight(cache_key(locator), visit_tool)

``visit_tool`` re-reads the cache before going to the tool, because an attempt
that finished a moment ago has already filled it. That re-read belongs to the
caller: this module knows about turn-taking, not about caches.

The leader's FAILURE is shared the same way. A failed fetch writes no cache
entry, so if the waiters ran the body themselves they would each miss and
visit the sick tool one after another (k-th waiter waits k x host_timeout).
Instead they get the leader's exception object — the real one, so the route's
ImageNotFound -> 404 / SourceUnavailable -> 503 mapping is unchanged.

Handing over the RESULT is what bounds a waiter's wait at one fetch. Waking
them one at a time to re-read the cache themselves would put k-1 cache reads
(a network round trip each, against MinIO at the office) in front of the k-th
waiter's response — on top of a fetch that may already be running to
``ftp_host_timeout``, under a uWSGI ``harakiri`` that is only twice that.

A failure is NOT remembered: the attempt is removed from the registry before
its waiters are woken, so anyone arriving after it is a fresh attempt and goes
to the tool. A recovering tool is never masked by a cached error. The flip
side is that this is not mutual exclusion — a new attempt can start while the
previous one's waiters are still finishing — and it does not need to be, since
what we deduplicate is the visit, not the turn.

Deliberately per-process and lock-free of any store: with one worker it is
exact, and with several the duplication drops from unbounded to the worker
count, which the shared MinIO cache already absorbs. A Redis lease would add
TTLs, polling and failure modes to buy that last factor.

There is no timeout. A waiter blocking IS the intent — the alternative is
giving up and going to the tool, which is the load this exists to prevent —
and a waiter's wait is bounded by ONE fetch (ftp_timeout / host_timeout),
because the attempt it waits on ends the whole queue either way.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar, cast

T = TypeVar("T")

# Distinguishes "the leader produced None" from "the leader produced nothing",
# which are different answers for a waiter (take it vs. run your own).
_MISSING: object = object()


class _Attempt:
    """One in-flight visit to the tool, plus everyone queued behind it.

    ``done`` is set once, by the leader, and wakes every waiter at the same
    moment; ``outcome`` and ``error`` are what they read when they wake.
    """

    __slots__ = ("done", "error", "outcome")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.error: Exception | None = None
        self.outcome: object = _MISSING


# key -> the attempt currently in flight. Present only while its leader is
# inside: the leader deletes it BEFORE waking the waiters, so a later arrival
# can never join a finished attempt (and never inherits its failure).
_attempts: dict[str, _Attempt] = {}
_registry_guard = threading.Lock()


def single_flight(key: str, fetch: Callable[[], T]) -> T:
    """Run ``fetch`` once for ``key``, however many callers ask at once.

    The first caller (the leader) runs it. Callers that arrive while it runs
    wait, and then get the leader's return value — or, if it raised, that same
    exception — without running ``fetch`` themselves.
    """
    with _registry_guard:
        attempt = _attempts.get(key)
        leading = attempt is None
        if attempt is None:
            attempt = _Attempt()
            _attempts[key] = attempt

    if not leading:
        attempt.done.wait()
        if attempt.error is not None:
            raise attempt.error
        if attempt.outcome is not _MISSING:
            return cast("T", attempt.outcome)
        # Neither a value nor an error: the leader died of something that is
        # not about the tool at all (KeyboardInterrupt/SystemExit — see the
        # `except Exception` below). Nothing was shared, so take our own turn.
        return fetch()

    try:
        attempt.outcome = fetch()
    except Exception as exc:
        # Shared with the waiters already queued behind this attempt. Only
        # Exception: a KeyboardInterrupt/SystemExit is about THIS thread dying,
        # not about the tool, and must not be re-raised in someone else's.
        attempt.error = exc
        raise
    finally:
        with _registry_guard:
            # Unpublish first, then wake: what is left in the registry is only
            # ever an attempt still in flight.
            del _attempts[key]
        attempt.done.set()
    return cast("T", attempt.outcome)
