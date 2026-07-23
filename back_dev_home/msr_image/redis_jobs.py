"""Redis-backed JobRegistry for office multi-worker deployments (Phase 2/3).

``MemoryJobRegistry`` keeps job state in process memory, which is correct at
home and for a single worker. Under ``gunicorn -w N`` it is not: the worker
that accepts ``POST /api/msr-images`` and the worker that answers the client's
poll are different processes, so the poll would 404 a job that is running
perfectly well next door. This registry moves that state to Redis, which every
worker already shares.

Layout — one hash per job, one list per job's failures:

    skewnono:msr_image:job:<job_id>   HASH  job_id status total done ok ng
    skewnono:msr_image:fail:<job_id>  LIST  JSON {name, error} per failure

Separate prefixes, not a ``:failures`` suffix, so the job scan in
:meth:`running_count` can never trip over a list key (a ``HGET`` against one is
a WRONGTYPE error).

Counters move with ``HINCRBY`` rather than read-modify-write: the bounded
download pool reports from several threads at once, and a get/put race would
silently lose ticks. Every key carries ``SKEWNONO_MSR_IMAGE_JOB_TTL``, refreshed
on each update, so finished jobs drain on their own and a worker that dies
mid-download cannot pin a slot in the ``max_jobs`` gate forever.

Office-only: ``jobs.make_registry`` imports this module lazily, and the Redis
client itself is resolved on first use through the shared office plumbing.
"""

import json
import uuid
from collections.abc import Callable
from typing import cast

from back_dev_home.msr_image.contracts import DownloadFailure, DownloadJobStatus

_JOB_PREFIX = "skewnono:msr_image:job"
_FAIL_PREFIX = "skewnono:msr_image:fail"


def _default_client():
    # Lazy: office-only dependency, keeps the home boot path free of Redis.
    from back_dev_home._runtime.office_redis import redis_client

    return redis_client()


def _text(value) -> str:
    """The shared office client runs ``decode_responses=False`` (its usual
    payloads are parquet DataFrames), so hash fields come back as bytes."""
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


class RedisJobRegistry:
    """Satisfies the same ``JobRegistry`` Protocol as ``MemoryJobRegistry``."""

    def __init__(self, job_ttl: int = 3600, client_factory: Callable[[], object] | None = None):
        self.job_ttl = job_ttl
        self._factory = client_factory or _default_client
        self._client = None

    @property
    def client(self):
        # Resolved on first use, not in __init__: selecting this registry must
        # not open a connection (mirrors MinioImageCache).
        if self._client is None:
            self._client = self._factory()
        return self._client

    def _job_key(self, job_id: str) -> str:
        return f"{_JOB_PREFIX}:{job_id}"

    def _fail_key(self, job_id: str) -> str:
        return f"{_FAIL_PREFIX}:{job_id}"

    def _touch(self, job_id: str) -> None:
        """Re-arm the TTL so an active job never expires under its own worker.
        EXPIRE on a missing key is a no-op, so the failures key needs no guard."""
        self.client.expire(self._job_key(job_id), self.job_ttl)
        self.client.expire(self._fail_key(job_id), self.job_ttl)

    def create(self, total: int) -> str:
        job_id = uuid.uuid4().hex
        key = self._job_key(job_id)
        self.client.hset(
            key,
            mapping={
                "job_id": job_id,
                "status": "running",
                "done": 0,
                "total": total,
                "ok": 0,
                "ng": 0,
            },
        )
        self.client.expire(key, self.job_ttl)
        return job_id

    def create_bounded(self, total: int, max_running: int) -> str | None:
        """Refuse at the cap, else create.

        Unlike the in-process registry this is not one atomic step: two workers
        POSTing in the same instant can both pass the count. That is an accepted
        overshoot for a soft resource guard — worst case a few extra concurrent
        downloads — and it is self-correcting, because job keys expire rather
        than leaking slots. Making it strictly atomic would need a Lua script,
        which buys little here and cannot be exercised at home.
        """
        if self.running_count() >= max_running:
            return None
        return self.create(total)

    def running_count(self) -> int:
        count = 0
        for raw_key in self.client.scan_iter(match=f"{_JOB_PREFIX}:*"):
            status = self.client.hget(_text(raw_key), "status")
            if status is not None and _text(status) == "running":
                count += 1
        return count

    def get(self, job_id: str) -> DownloadJobStatus | None:
        raw = self.client.hgetall(self._job_key(job_id))
        fields = {_text(k): _text(v) for k, v in raw.items()}
        # No status field means this is not a job we created — either it expired
        # or a late counter write recreated the key. Report it unknown (404)
        # rather than inventing a half-populated status.
        if "status" not in fields:
            return None
        failures: list[DownloadFailure] = [
            json.loads(_text(item))
            for item in self.client.lrange(self._fail_key(job_id), 0, -1)
        ]
        return cast(
            DownloadJobStatus,
            {
                "job_id": fields.get("job_id", job_id),
                "status": fields["status"],
                "done": int(fields.get("done", 0)),
                "total": int(fields.get("total", 0)),
                "ok": int(fields.get("ok", 0)),
                "ng": int(fields.get("ng", 0)),
                "failures": failures,
            },
        )

    def set_total(self, job_id: str, total: int) -> None:
        self.client.hset(self._job_key(job_id), "total", total)
        self._touch(job_id)

    def record_ok(self, job_id: str) -> None:
        key = self._job_key(job_id)
        self.client.hincrby(key, "done", 1)
        self.client.hincrby(key, "ok", 1)
        self._touch(job_id)

    def record_failure(self, job_id: str, name: str, error: str) -> None:
        key = self._job_key(job_id)
        self.client.hincrby(key, "done", 1)
        self.client.hincrby(key, "ng", 1)
        self.client.rpush(self._fail_key(job_id), json.dumps({"name": name, "error": error}))
        self._touch(job_id)

    def finish(self, job_id: str) -> None:
        self.client.hset(self._job_key(job_id), "status", "done")
        self._touch(job_id)  # settled state still expires: job_ttl from now

    def mark_error(self, job_id: str) -> None:
        self.client.hset(self._job_key(job_id), "status", "error")
        self._touch(job_id)
