"""Job-run records, in memory at home and in a Redis list at the office.

Both backends satisfy :class:`RunLog`. ``wrap`` lives here rather than in the
registry so the start/end/error bracketing is defined once and both backends
get it.

Every write failure is swallowed-and-logged. Observability must never break the
task it observes -- a Redis blip should not turn a working purge into a failed
one.
"""

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any, Protocol
from zoneinfo import ZoneInfo

log = logging.getLogger("skewnono.scheduler")

KST = ZoneInfo("Asia/Seoul")


def kst_stamp() -> str:
    """Second-precision aware-KST ISO timestamp -- the one format records use.

    KST rather than UTC because nothing renders these: /api/health/jobs returns
    the record verbatim and there is no jobs UI, so the stored string *is* what
    an operator in Korea reads.

    It also has to match its neighbours. The scheduler runs on
    ``cfg.timezone = "Asia/Seoul"``, so the ``scheduled`` field a "missed"
    record carries (APScheduler's ``scheduled_run_time``, see
    ``_install_missed_listener``) is already +09:00 -- a UTC ``ts`` beside it
    put the two most comparable fields in one record nine hours apart.

    Still offset-aware, so records stay comparable across hosts and a Redis
    list holding both the old +00:00 entries and new +09:00 ones is read
    correctly. Nothing sorts on this field -- ``read`` preserves LPUSH order.
    """
    return datetime.now(KST).isoformat(timespec="seconds")


class RunLog(Protocol):
    def record(self, job: str, event: str, **extra: Any) -> None: ...
    def read(self, limit: int) -> list[dict[str, Any]]: ...
    def wrap(self, fn: Callable, name: str) -> Callable: ...


class _WrapMixin:
    def wrap(self, fn: Callable, name: str) -> Callable:
        """Emit start / end / error around each call.

        ``name`` is the registry key, never ``fn.__name__``: the key is the
        job's identity for the lock, the scheduler job id and these records,
        and deriving one of them differently splits that identity.
        """

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.record(name, "start")  # type: ignore[attr-defined]
            started = time.monotonic()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                self.record(  # type: ignore[attr-defined]
                    name,
                    "error",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error=repr(exc),
                )
                raise
            self.record(  # type: ignore[attr-defined]
                name,
                "end",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            return result

        return wrapper


def _build(job: str, event: str, extra: dict[str, Any]) -> dict[str, Any]:
    record = {"ts": kst_stamp(), "job": job, "event": event}
    record.update(extra)
    return record


class MemoryRunLog(_WrapMixin):
    """Home backend. A bounded deque, newest first.

    Per-process, which is correct at home: election guarantees one scheduler
    process, and that same process answers /api/health/jobs.
    """

    def __init__(self, max_records: int = 500) -> None:
        self._records: deque[dict[str, Any]] = deque(maxlen=max_records)

    def record(self, job: str, event: str, **extra: Any) -> None:
        record = _build(job, event, extra)
        log.info("task-run %s", record)
        self._records.appendleft(record)

    def read(self, limit: int) -> list[dict[str, Any]]:
        return list(self._records)[:limit]


class RedisRunLog(_WrapMixin):
    """Office backend. LPUSH + LTRIM in one round-trip.

    Shared across workers on purpose: the elected worker writes, and any worker
    can answer /api/health/jobs.
    """

    def __init__(self, client, key: str, max_records: int = 500) -> None:
        self.client = client
        self.key = key
        self.max_records = max_records

    def record(self, job: str, event: str, **extra: Any) -> None:
        record = _build(job, event, extra)
        log.info("task-run %s", record)
        try:
            with self.client.pipeline() as pipe:
                pipe.lpush(self.key, json.dumps(record))
                pipe.ltrim(self.key, 0, self.max_records - 1)
                pipe.execute()
        except Exception:
            log.exception("failed to push task-run record")

    def read(self, limit: int) -> list[dict[str, Any]]:
        try:
            raw = self.client.lrange(self.key, 0, limit - 1)
        except Exception:
            log.exception("failed to read task-run records")
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            try:
                out.append(json.loads(item))
            except (ValueError, TypeError):
                # Lenient, like the rest of this module: one malformed entry
                # must not hide the records around it.
                log.warning("dropping malformed task-log entry: %r", item)
        return out


def make_run_log(cfg) -> RunLog:
    """Pick the backend by mode. Office falls back to memory if Redis is not
    configured -- a scheduler with no run log is far better than no scheduler."""
    from back_dev_home._runtime.data_provider import get_mode

    if get_mode() == "mock":
        return MemoryRunLog(cfg.log_list_max)
    from back_dev_home._runtime.office_redis import redis_client_or_none

    client = redis_client_or_none()
    if client is None:
        log.warning("office mode but Redis is unconfigured; run log is memory-only")
        return MemoryRunLog(cfg.log_list_max)
    return RedisRunLog(client, cfg.log_list_key, cfg.log_list_max)
