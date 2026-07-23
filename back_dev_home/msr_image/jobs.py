"""Download-all job state. We own the observable state (memory at home / single
worker; Redis keys across office workers); ftp_handler/threads only execute."""

import os
import threading
import uuid
from typing import Protocol

from back_dev_home.msr_image.contracts import DownloadJobStatus


class JobRegistry(Protocol):
    def create(self, total: int) -> str: ...
    def create_bounded(self, total: int, max_running: int) -> str | None: ...
    def get(self, job_id: str) -> DownloadJobStatus | None: ...
    def running_count(self) -> int: ...
    def set_total(self, job_id: str, total: int) -> None: ...
    def record_ok(self, job_id: str) -> None: ...
    def record_failure(self, job_id: str, name: str, error: str) -> None: ...
    def finish(self, job_id: str) -> None: ...
    def mark_error(self, job_id: str) -> None: ...


class MemoryJobRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, DownloadJobStatus] = {}

    def _new(self, total: int) -> DownloadJobStatus:
        job_id = uuid.uuid4().hex
        return {
            "job_id": job_id,
            "status": "running",
            "done": 0,
            "total": total,
            "ok": 0,
            "ng": 0,
            "failures": [],
        }

    def create(self, total: int) -> str:
        with self._lock:
            st = self._new(total)
            self._jobs[st["job_id"]] = st
        return st["job_id"]

    def create_bounded(self, total: int, max_running: int) -> str | None:
        """Atomically refuse when at the cap, else create. Closes the race a
        separate running_count()+create() would leave open under concurrent POSTs."""
        with self._lock:
            running = sum(1 for s in self._jobs.values() if s["status"] == "running")
            if running >= max_running:
                return None
            st = self._new(total)
            self._jobs[st["job_id"]] = st
            return st["job_id"]

    def get(self, job_id: str) -> DownloadJobStatus | None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is None:
                return None
            # Full snapshot: copy the nested failures list + each entry so a
            # caller can't mutate internal state through the returned dict.
            return {**st, "failures": [dict(f) for f in st["failures"]]}  # type: ignore[return-value]

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for st in self._jobs.values() if st["status"] == "running")

    def set_total(self, job_id: str, total: int) -> None:
        """Fill in the size once the listing knows it.

        A job is minted before the directory listing runs (so the POST can
        answer 202 without waiting on the tool), which means it starts at an
        unknown total of 0 and learns the real count here."""
        with self._lock:
            st = self._jobs.get(job_id)
            if st is not None:
                st["total"] = total

    def record_ok(self, job_id: str) -> None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is not None:
                st["done"] += 1
                st["ok"] += 1

    def record_failure(self, job_id: str, name: str, error: str) -> None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is not None:
                st["done"] += 1
                st["ng"] += 1
                st["failures"].append({"name": name, "error": error})

    def finish(self, job_id: str) -> None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is not None:
                st["status"] = "done"

    def mark_error(self, job_id: str) -> None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is not None:
                st["status"] = "error"


_DEFAULT_REGISTRY = MemoryJobRegistry()


def default_registry() -> MemoryJobRegistry:
    """Process-wide registry so route handlers and the worker thread share state."""
    return _DEFAULT_REGISTRY


def make_registry(cfg, provider: str) -> JobRegistry:
    """Pick the job store that matches how this instance is deployed.

    Job state only has to leave the process when requests can land on a
    different one. That needs both halves to be true: an office adapter is
    active AND Redis is configured. Office alone is not enough — a single-worker
    office run with no Redis must keep working — and Redis alone says nothing,
    since a home instance may have REDIS_* set for other features.

    ``cfg`` is an ImageConfig, typed loosely to avoid a config import cycle.
    """
    if provider == "office" and os.environ.get("REDIS_HOST"):
        # Office-only import: the home boot path never pulls this in.
        from back_dev_home.msr_image.redis_jobs import RedisJobRegistry

        return RedisJobRegistry(job_ttl=cfg.job_ttl)
    return _DEFAULT_REGISTRY
