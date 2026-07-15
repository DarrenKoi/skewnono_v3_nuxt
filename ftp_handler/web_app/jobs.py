"""Run fleet FTP collection off the request thread in a web app.

``FtpFleetDownloader.download()`` is synchronous and blocks its caller for the
whole fleet run (up to ``host_timeout`` per stalled host). Calling it inside a
Flask request handler ties up that worker for minutes and every concurrent
request spawns its own fan-out pool. This module runs the work on a background
thread instead: ``submit()`` returns a job id immediately so the HTTP response
goes out at once, and the result is fetched later by polling ``get()``.

Stdlib only (``ThreadPoolExecutor`` + a lock-guarded registry) — importable on a
worker that has neither ``flask`` nor ``requests``; the optional Flask blueprint
imports ``flask`` lazily, only when you call ``create_jobs_blueprint``.

Single-process scope:
  The job registry lives in the process that submitted the job. Under a
  multi-process WSGI server (``gunicorn -w N``) a status poll may land on a
  different worker that never saw the job and returns 404. For that case run the
  collector in ONE dedicated process (e.g. an APScheduler/worker process that
  also serves the status endpoint) or back the registry with Redis. For a dev
  server, an embedded single scheduler, or a single-worker deployment, this is
  all you need.

When you do NOT need this:
  If the run is purely scheduled (no HTTP trigger), an APScheduler job already
  executes on its own thread and never blocks a request — just call
  ``downloader.download(specs)`` from the scheduled function directly. Reach for
  ``BackgroundJobs`` when a request must KICK OFF a run and return before it
  finishes.

    from ftp_handler.ftp_fleet_jobs import BackgroundJobs, create_jobs_blueprint
    from ftp_handler.ftp_fleet_downloader import FtpFleetDownloader, save_to_dir
    from ftp_handler.eqp_ftp_collect import build_host_specs

    jobs = BackgroundJobs()                      # one fleet run at a time

    def start(body: dict) -> str:
        specs = build_host_specs(body["fleet"])
        dl = FtpFleetDownloader(user=body["user"], password=body["password"])
        return jobs.submit(lambda: dl.download(specs, on_file=save_to_dir(body["dest"])))

    app.register_blueprint(create_jobs_blueprint(jobs, start=start))
    # POST /fleet/jobs {fleet,...} -> 202 {"job_id": "..."}
    # GET  /fleet/jobs/<job_id>    -> 200 {status, result-counts, error}
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

# Job timestamps follow the project convention: ingested/stamped times are KST.
_TZ = ZoneInfo("Asia/Seoul")


@dataclass(slots=True)
class Job:
    """One background unit of work and its outcome.

    ``status`` is ``"running"`` until the work returns (``"done"``) or raises
    (``"error"``). ``result`` holds whatever the submitted callable returned
    (e.g. a ``DownloadReport``); ``error`` holds the exception text on failure.
    """

    id: str
    status: str
    submitted_at: datetime
    finished_at: datetime | None = None
    result: object | None = None
    error: str | None = None


class BackgroundJobs:
    """A tiny lock-guarded job runner over a ``ThreadPoolExecutor``.

    ``submit()`` returns immediately with a job id; the work runs on a background
    thread so the calling (request) thread is never blocked. ``get()`` returns a
    snapshot of the job's current state for status polling.

    ``max_workers=1`` (default) runs one fleet collection at a time — extra
    submits queue — mirroring the DAG's ``max_active_runs=1``. The downloader
    already fans out internally to ``max_concurrency`` connections, so you rarely
    want more than one concurrent fleet run.
    """

    def __init__(self, *, max_workers: int = 1, keep_last: int = 200) -> None:
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="fleet-job"
        )
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._keep_last = keep_last

    def submit(self, work: Callable[[], object]) -> str:
        """Schedule ``work`` on a background thread; return its job id at once."""
        job_id = uuid4().hex
        with self._lock:
            self._jobs[job_id] = Job(
                id=job_id, status="running", submitted_at=datetime.now(_TZ)
            )
            self._evict_locked()
        self._pool.submit(self._run, job_id, work)
        return job_id

    def get(self, job_id: str) -> Job | None:
        """Return a snapshot of ``job_id``'s state, or ``None`` if unknown.

        A copy is returned so the caller never observes a half-updated job while
        the worker thread is mutating it.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            return replace(job) if job is not None else None

    def shutdown(self) -> None:
        """Stop accepting new jobs; running jobs finish in the background."""
        self._pool.shutdown(wait=False)

    def _run(self, job_id: str, work: Callable[[], object]) -> None:
        try:
            result, status, error = work(), "done", None
        except Exception as exc:  # noqa: BLE001 - any failure becomes job state
            result, status, error = None, "error", f"{type(exc).__name__}: {exc}"
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:  # may have been evicted under extreme churn
                job.result = result
                job.status = status
                job.error = error
                job.finished_at = datetime.now(_TZ)

    def _evict_locked(self) -> None:
        # Drop the oldest FINISHED jobs once the registry grows past keep_last so
        # a long-lived server doesn't accumulate completed jobs forever. Running
        # jobs are never evicted. Caller holds self._lock.
        if len(self._jobs) <= self._keep_last:
            return
        finished = sorted(
            (j for j in self._jobs.values() if j.status != "running"),
            key=lambda j: j.submitted_at,
        )
        for job in finished[: len(self._jobs) - self._keep_last]:
            del self._jobs[job.id]


def summarize(result: object) -> dict | None:
    """Counts-only view of a fleet report for a status response — never bytes.

    Works for ``DownloadReport`` and ``ListingReport`` (both expose
    ``ok``/``ng``/``failures``). Returns ``None`` for anything else; if your work
    returns a custom result, serialize it yourself rather than through here. The
    point is to never ship raw file bytes (a report can hold the whole fleet) in
    a JSON status response.
    """
    if not hasattr(result, "failures"):
        return None
    out: dict = {"ok": result.ok, "ng": result.ng}
    if hasattr(result, "failure_ratio"):
        out["failure_ratio"] = round(result.failure_ratio, 3)
    if hasattr(result, "total_paths"):
        out["total_paths"] = result.total_paths
    out["failures"] = [
        {"host": f.host, "error": f.error, "remote_path": f.remote_path}
        for f in result.failures
    ]
    return out


def job_to_dict(job: Job) -> dict:
    """Serialize a ``Job`` for an HTTP status response (no file bytes)."""
    return {
        "job_id": job.id,
        "status": job.status,
        "submitted_at": job.submitted_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "result": summarize(job.result) if job.status == "done" else None,
        "error": job.error,
    }


def create_jobs_blueprint(jobs: BackgroundJobs, *, start: Callable[[dict], str]):
    """Build a Flask Blueprint exposing job submit + status.

    ``start`` receives the POST body (parsed JSON) and must kick off the work via
    ``jobs.submit(...)`` and return the job id. Keeping ``start`` in your app
    means this blueprint never has to know how you build specs or where
    credentials come from. ``flask`` is imported lazily here so the rest of the
    module stays usable on a worker without flask installed.

    Routes:
        POST /fleet/jobs       -> 202 {"job_id": ...}
        GET  /fleet/jobs/<id>  -> 200 status / 404 if unknown
    """
    from flask import Blueprint, jsonify, request

    bp = Blueprint("fleet_jobs", __name__)

    @bp.post("/fleet/jobs")
    def create_job():
        job_id = start(request.get_json(force=True) or {})
        return jsonify({"job_id": job_id}), 202

    @bp.get("/fleet/jobs/<job_id>")
    def get_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            return jsonify({"error": "unknown job"}), 404
        return jsonify(job_to_dict(job))

    return bp
