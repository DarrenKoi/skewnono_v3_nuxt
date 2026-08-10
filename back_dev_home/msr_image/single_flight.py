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

Deliberately per-process and lock-free of any store: with one worker it is
exact, and with several the duplication drops from unbounded to the worker
count, which the shared MinIO cache already absorbs. A Redis lease would add
TTLs, polling and failure modes to buy that last factor.

There is no timeout. A waiter blocking IS the intent — the alternative is
giving up and going to the tool, which is the load this exists to prevent —
and the fetch it waits on is already bounded by ftp_timeout / host_timeout.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

# key -> (lock, how many callers hold or await it). The count is what lets the
# entry be removed safely: dropping it while someone still waits would hand the
# next arrival a different lock object and silently lose the exclusion.
_locks: dict[str, tuple[threading.Lock, int]] = {}
_registry_guard = threading.Lock()


@contextmanager
def fetch_gate(key: str) -> Iterator[None]:
    """Serialise callers sharing ``key``; release and clean up on the way out."""
    with _registry_guard:
        lock, waiting = _locks.get(key, (threading.Lock(), 0))
        _locks[key] = (lock, waiting + 1)

    lock.acquire()
    try:
        yield
    finally:
        lock.release()
        with _registry_guard:
            held, waiting = _locks[key]
            if waiting <= 1:
                del _locks[key]
            else:
                _locks[key] = (held, waiting - 1)
