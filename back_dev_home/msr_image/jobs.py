"""Download-all job state. We own the observable state (memory at home / single
worker; Redis keys across office workers); ftp_handler/threads only execute."""

import threading
import uuid
from typing import Protocol

from back_dev_home.msr_image.contracts import DownloadJobStatus


class JobRegistry(Protocol):
    def create(self, total: int) -> str: ...
    def get(self, job_id: str) -> DownloadJobStatus | None: ...
    def record_ok(self, job_id: str) -> None: ...
    def record_failure(self, job_id: str, name: str, error: str) -> None: ...
    def finish(self, job_id: str) -> None: ...


class MemoryJobRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, DownloadJobStatus] = {}

    def create(self, total: int) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "done": 0,
                "total": total,
                "ok": 0,
                "ng": 0,
                "failures": [],
            }
        return job_id

    def get(self, job_id: str) -> DownloadJobStatus | None:
        with self._lock:
            st = self._jobs.get(job_id)
            if st is None:
                return None
            # Full snapshot: copy the nested failures list + each entry so a
            # caller can't mutate internal state through the returned dict.
            return {**st, "failures": [dict(f) for f in st["failures"]]}  # type: ignore[return-value]

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


_DEFAULT_REGISTRY = MemoryJobRegistry()


def default_registry() -> MemoryJobRegistry:
    """Process-wide registry so route handlers and the worker thread share state."""
    return _DEFAULT_REGISTRY
