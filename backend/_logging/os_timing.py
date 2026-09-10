"""Per-request OpenSearch round-trip accounting, folded into the request log.

`activity.py` already writes exactly one log document per request. This module
adds four fields to that document rather than emitting a line per query, and
the reason is the thing being measured: the log handler ships to the same
OpenSearch cluster the queries hit, through one bounded queue shared with the
audit rows. A line per query would multiply the document count by the very
fan-out under investigation, and under load the queue would drop audit rows to
make room for its own instrumentation.

What the four fields answer, which no single number can:

* ``query_count`` — the decision variable. Batching removes round trips, not
  query time, so a screen that already makes one has nothing to gain.
* ``total_ms`` vs. the request's ``latency_ms`` — whether OpenSearch is even
  where the time goes.
* ``slowest_ms`` vs. ``total_ms`` — whether the time is in the count (many
  small queries, batchable) or in one dominant query (not batchable; that
  query is the bug).
* ``slowest_index`` — which index to open first, so one office trip is enough.

Deliberately Flask-free: the two query helpers in ``ebeam/_office_search.py``
also run from standalone diagnostics and scheduler jobs, where there is no
request. With no collector installed ``record()`` returns immediately, so
those callers never learn this module exists.
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator


__all__ = ["OsTimingSummary", "collect", "finish", "record", "start", "summary"]


@dataclass
class OsTimingSummary:
    query_count: int
    total_ms: int
    slowest_ms: int
    slowest_index: str

    def as_extra(self) -> dict[str, Any]:
        return {
            "opensearch_query_count": self.query_count,
            "opensearch_total_ms": self.total_ms,
            "opensearch_slowest_ms": self.slowest_ms,
            "opensearch_slowest_index": self.slowest_index,
        }


class _Collector:
    def __init__(self) -> None:
        self.query_count = 0
        # Kept as float and rounded once at the end: rounding each query would
        # turn a screen of forty sub-millisecond queries into a 0 ms total.
        self.total_ms = 0.0
        self.slowest_ms = 0.0
        self.slowest_index = ""

    def add(self, index: str, elapsed_ms: float) -> None:
        self.query_count += 1
        self.total_ms += elapsed_ms
        if elapsed_ms >= self.slowest_ms:
            self.slowest_ms = elapsed_ms
            self.slowest_index = index


_collector: ContextVar[_Collector | None] = ContextVar("os_timing", default=None)


def record(index: str, elapsed_ms: float) -> None:
    """Attribute one OpenSearch round trip to the request in flight, if any."""
    collector = _collector.get()
    if collector is None:
        return
    collector.add(index, elapsed_ms)


def summary() -> OsTimingSummary | None:
    """The request's round trips, or None when it made none.

    None rather than a zero-filled summary on purpose: the log handler omits
    None-valued extras, so a request that never touched OpenSearch leaves no
    ``opensearch_*`` fields behind instead of four zeroes per static asset.
    """
    collector = _collector.get()
    if collector is None or collector.query_count == 0:
        return None
    return OsTimingSummary(
        query_count=collector.query_count,
        total_ms=round(collector.total_ms),
        slowest_ms=round(collector.slowest_ms),
        slowest_index=collector.slowest_index,
    )


def start() -> Token[_Collector | None]:
    """Begin collecting, returning the token that ends it.

    Split from ``collect`` because Flask hands the request lifecycle out as two
    callbacks rather than a block; ``activity.py`` starts in ``before_request``
    and finishes in ``teardown_request``.
    """
    return _collector.set(_Collector())


def finish(token: Token[_Collector | None] | None) -> None:
    """End collection. Load-bearing rather than tidy: uWSGI reuses request
    threads, so a collector left installed bills the next request for queries
    this one made."""
    if token is not None:
        _collector.reset(token)


@contextmanager
def collect() -> Iterator[None]:
    """Collect for the duration of a block, for callers that have one."""
    token = start()
    try:
        yield
    finally:
        finish(token)
