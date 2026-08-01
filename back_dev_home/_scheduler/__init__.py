"""One scheduler for the whole backend.

``start_scheduler(app)`` is the only thing the app factory calls. It is
idempotent and safe to call from every worker: workers that lose the election
return None without creating a thread.

APScheduler's DEFAULT memory jobstore is used on purpose, in both phases. Jobs
here are declared in code and rebuilt every boot, and all three triggers are
cron -- absolute wall-clock -- so a fresh scheduler after a restart computes
exactly the right next fire. A RedisJobStore would pickle each job, and
pickling a functools.wraps-decorated closure follows __qualname__ back to the
BARE task, so a restored job would bypass the lock and the run log entirely.
The accepted loss: a run missed while the process is down is skipped rather
than detected as missed.
"""

import atexit
import logging

from back_dev_home._scheduler.config import load_scheduler_config
from back_dev_home._scheduler.election import is_scheduler_worker
from back_dev_home._scheduler.registry import JOB_REGISTRY, build_jobs
from back_dev_home._scheduler.runlog import make_run_log

logger = logging.getLogger("skewnono.scheduler")

__all__ = ["start_scheduler"]

_EXTENSION_KEY = "scheduler"


def start_scheduler(app):
    """Start the scheduler if this process owns it. Returns it, or None."""
    if app.testing:
        # A test suite creates many apps; each would otherwise leave a live
        # thread firing real jobs.
        return None
    if _EXTENSION_KEY in app.extensions:
        return app.extensions[_EXTENSION_KEY]

    cfg = load_scheduler_config()
    run_log = make_run_log(cfg)
    # Set even on workers that lose the election: any worker may serve
    # /api/health/jobs, and at the office they all read the same Redis list.
    app.extensions["scheduler_run_log"] = run_log

    if not is_scheduler_worker(app):
        logger.info("not the scheduler process; serving requests only")
        return None

    from apscheduler.schedulers.background import BackgroundScheduler

    jobs = build_jobs(cfg, run_log)
    scheduler = BackgroundScheduler(daemon=True, timezone=cfg.timezone)
    for name, spec in JOB_REGISTRY.items():
        scheduler.add_job(
            jobs[name],
            trigger=spec["trigger"],
            id=name,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=spec.get("misfire_grace_time"),
        )
    _install_missed_listener(scheduler, run_log)
    scheduler.start()
    app.extensions[_EXTENSION_KEY] = scheduler
    atexit.register(_shutdown, scheduler)
    logger.info("scheduler started with %d jobs", len(JOB_REGISTRY))
    return scheduler


def _install_missed_listener(scheduler, run_log) -> None:
    """Record dropped and refused fires.

    Without this they leave NO record at all -- their only trace is a line in
    the uWSGI log, which at the office nobody may be reading.
    """
    from apscheduler.events import EVENT_JOB_MAX_INSTANCES, EVENT_JOB_MISSED

    def record(event) -> None:
        if event.code == EVENT_JOB_MISSED:
            reason = "start missed by more than misfire_grace_time"
            scheduled = getattr(event, "scheduled_run_time", None)
        else:
            reason = "previous run still executing (max_instances)"
            times = getattr(event, "scheduled_run_times", None) or []
            scheduled = times[0] if times else None
        run_log.record(
            event.job_id,
            "missed",
            reason=reason,
            scheduled=scheduled.isoformat() if scheduled else None,
        )

    scheduler.add_listener(record, EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES)


def _shutdown(scheduler) -> None:
    """Pause BEFORE shutdown.

    Without the pause, a trigger tick mid-flight can call submit_job() after
    the ThreadPoolExecutor has been torn down, producing sporadic "cannot
    schedule new futures after shutdown" errors. With max-requests = 1000 in
    wsgi.ini, worker recycles are routine here, not rare.
    """
    try:
        if scheduler.running:
            scheduler.pause()
            scheduler.shutdown(wait=False)
    except Exception:
        pass
