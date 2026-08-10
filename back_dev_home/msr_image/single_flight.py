"""Keep concurrent requests for ONE image to one visit to the tool.

The measuring tool's FTP server caps concurrent sessions and engineers use
their own tools against the same equipment, so a session is a shared, scarce
resource. Two things make us open more of them than we need: the browser
re-requests a slow image at 2.5s and 5s (utils/imageRetry.ts), and two people
can open the same MSR at once. Both arrive as concurrent requests for the SAME
cache key, and each used to open its own session.

This module only provides the mutual exclusion. The dedup comes from the
caller re-reading the cache while holding the gate:

    with fetch_gate(cache_key(locator)):
        hit = cache.get(locator)          # did the request ahead of us fill it?
        if hit is not None:
            return hit                    # no tool visit
        ...

Without that re-read the waiters would simply take turns visiting the tool,
which is slower and no lighter.

The re-read only dedups when the leader SUCCEEDS — a failed fetch writes no
cache entry, so every waiter would miss, and they would visit the sick tool
one after another (k-th waiter waits k x host_timeout). So the leader's
failure is shared: whoever is queued behind an attempt that raises gets that
same exception instead of taking a turn. This costs no generality — the
exception object is the real one, so the route's ImageNotFound -> 404 /
SourceUnavailable -> 503 mapping is unchanged.

A failure is NOT remembered: the attempt is removed from the registry before
its waiters are woken, so anyone arriving after it is a fresh attempt and goes
to the tool. A recovering tool is never masked by a cached error.

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
from collections.abc import Iterator
from contextlib import contextmanager


class _Attempt:
    """One in-flight visit to the tool, plus everyone queued behind it.

    ``lock`` is taken by the leader for the whole body and released on the way
    out, so waiters block on it; ``error`` is what the leader's body raised, and
    is read by the waiters once they wake.
    """

    __slots__ = ("error", "lock")

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.error: Exception | None = None


# key -> the attempt currently in flight. Present only while its leader is
# inside the gate: the leader deletes it BEFORE releasing the lock, so a later
# arrival can never join a finished attempt (and never inherits its failure).
_attempts: dict[str, _Attempt] = {}
_registry_guard = threading.Lock()


@contextmanager
def fetch_gate(key: str) -> Iterator[None]:
    """Serialise callers sharing ``key``.

    The first caller (the leader) runs the body. Callers that arrive while it
    is running block, and then either run their own body — the success path,
    where re-reading the cache turns their turn into a hit — or, if the leader
    raised, get that exception raised here instead of visiting the tool.
    """
    with _registry_guard:
        attempt = _attempts.get(key)
        leading = attempt is None
        if leading:
            attempt = _Attempt()
            attempt.lock.acquire()  # uncontended: unpublished, so nobody can hold it
            _attempts[key] = attempt

    if not leading:
        attempt.lock.acquire()
        try:
            if attempt.error is not None:
                raise attempt.error
            yield
        finally:
            attempt.lock.release()
        return

    try:
        yield
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
        attempt.lock.release()
