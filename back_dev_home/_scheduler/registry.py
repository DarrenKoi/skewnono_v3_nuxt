"""What runs, when, and with which knobs.

Four knobs matter, and for jobs measured in minutes the last two matter most.

``minute=``  Cron fires at an exact instant, so two jobs written ``minute=0``
             start TOGETHER, not "around" the hour. Every job gets its own
             slot; a test asserts no two share one.

``lock_ttl`` Orphan-clear window only -- a live run re-arms its own TTL, so it
             may overrun this freely. Smaller is better: it bounds how long a
             lock left by a killed process blocks the job. Every job here is
             daily or weekly, so any value under a day skips zero runs. Do NOT
             reason "weekly job, weekly TTL" -- that is this knob's most common
             mistake.

``misfire_grace_time``  How late a start may be and still happen. Checked when
             the job reaches a worker thread, so it covers queue wait. The 60s
             APScheduler default is far too tight for a WEEKLY job: a missed
             snapshot write does not retry until next Monday, so six hours of
             grace costs nothing and saves a week.

The *data* jobs all sit inside 01:00-08:00, the confirmed quiet window
(user-confirmed 2026-08-01), and the sweep deliberately follows the write. The
two host-maintenance jobs -- ``uwsgi_touch_reload`` and ``log_retention`` --
sit just after midnight instead, which is the point of them: the reload exists
to hand each working day a process that booted minutes ago, and the log sweep
follows it so the day's fresh log file is never a sweep candidate.

**Cron fields are stored, not triggers.** A ``CronTrigger`` built at import
time binds ``get_localzone()`` for good -- APScheduler never re-applies the
scheduler's own timezone to an already-constructed trigger, so
``SchedulerConfig.timezone`` would buy nothing and a UTC cloud host would fire
the "quiet window" jobs at 12:10 KST, mid-workday. ``build_schedule(cfg)``
constructs each trigger once the config is in hand, with ``timezone=`` passed
explicitly. Building them late also lets the purge hour come from
``IMAGE_CACHE_PURGE_HOUR``, whose config object is read at build time.
"""

from collections.abc import Callable

from apscheduler.triggers.cron import CronTrigger

from back_dev_home._scheduler.locks import make_job_lock
from back_dev_home._scheduler.tasks.device_statistics import (
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)
from back_dev_home._scheduler.tasks.image_cache import purge_image_cache
from back_dev_home._scheduler.tasks.log_retention import purge_old_logs
from back_dev_home._scheduler.tasks.uwsgi_reload import touch_reload

def _image_cache_purge_cron() -> dict:
    """Nightly. :10 keeps it clear of the two weekly slots below.

    The hour is ``IMAGE_CACHE_PURGE_HOUR`` (default 3), read here rather than
    hardcoded so the env var documented in ``.env.example`` and
    ``msr_image/MIGRATION.md`` -- including its coordination with the Airflow
    DAG at 03:35 KST -- keeps working. Read at build time, not import time, so
    an operator only has to restart.
    """
    from back_dev_home.msr_image.config import load_config as load_image_config

    return {"hour": load_image_config().purge_hour, "minute": 10}


def _weekly_snapshot_write_cron() -> dict:
    """Monday, because the snapshot key IS that week's Monday."""
    return {"day_of_week": "mon", "hour": 1, "minute": 0}


def _uwsgi_reload_cron() -> dict:
    """00:05 nightly (user-confirmed 2026-08-05), the one job outside the
    01:00-08:00 quiet window and outside it on purpose: the point is to start
    each day on a process that booted minutes ago, so it has to run before the
    day's work, not in the middle of the night's."""
    return {"hour": 0, "minute": 5}


def _log_retention_cron() -> dict:
    """00:20, deliberately after the reload rather than before.

    uWSGI opens the new day's log file as it comes back up, so sweeping
    afterwards means the file the fresh instance is writing to is the newest
    one in the directory -- never a file the sweep just considered. Fifteen
    minutes is far more than the reload needs; it costs nothing here."""
    return {"hour": 0, "minute": 20}


def _weekly_snapshot_sweep_cron() -> dict:
    """90 minutes after the write, never before: sweeping first could delete
    the oldest kept snapshot in the same hour the newest arrives, and a failed
    write would still trigger deletions."""
    return {"day_of_week": "mon", "hour": 2, "minute": 30}


JOB_REGISTRY: dict[str, dict] = {
    "image_cache_purge": {
        "fn": purge_image_cache,
        "cron": _image_cache_purge_cron,
        "lock_ttl": 600,
        "misfire_grace_time": 3600,
    },
    "uwsgi_touch_reload": {
        "fn": touch_reload,
        "cron": _uwsgi_reload_cron,
        # Short on purpose: the touch reloads the very worker holding this
        # lock, so the release may never run. 120s keeps the orphan from
        # outliving the reload it caused.
        "lock_ttl": 120,
        # A reload that starts late is still a reload; but one that slips past
        # the morning is worse than none, so grace stops at two hours.
        "misfire_grace_time": 7200,
    },
    "log_retention": {
        "fn": purge_old_logs,
        "cron": _log_retention_cron,
        "lock_ttl": 600,
        "misfire_grace_time": 3600,
    },
    "weekly_snapshot_write": {
        "fn": write_weekly_snapshot,
        "cron": _weekly_snapshot_write_cron,
        "lock_ttl": 600,
        # Six hours: the next retry would otherwise be next Monday.
        "misfire_grace_time": 21600,
    },
    "weekly_snapshot_sweep": {
        "fn": sweep_weekly_snapshots,
        "cron": _weekly_snapshot_sweep_cron,
        "lock_ttl": 600,
        "misfire_grace_time": 3600,
    },
}


def build_schedule(cfg, registry: dict[str, dict] | None = None) -> dict[str, CronTrigger]:
    """One ``CronTrigger`` per entry, all in ``cfg.timezone``.

    Constructing them here rather than at import is the whole point: a trigger
    built without ``timezone=`` binds ``get_localzone()`` permanently, and
    handing it to a ``BackgroundScheduler(timezone=...)`` does NOT retag it.
    """
    registry = JOB_REGISTRY if registry is None else registry
    return {
        name: CronTrigger(timezone=cfg.timezone, **spec["cron"]())
        for name, spec in registry.items()
    }


def _skip_recorder(run_log, job: str) -> Callable[[dict], None]:
    """Build the on_skip callback for ``job``.

    A factory, not a closure written inline in the loop below: an inline
    closure captures the loop VARIABLE, so by the time any job ran, every
    callback would report the last-registered name.
    """

    def record_skip(info: dict) -> None:
        run_log.record(job, "skip", **info)

    return record_skip


def build_jobs(cfg, run_log, registry: dict[str, dict] | None = None) -> dict[str, Callable]:
    """Wrap every entry as ``job_lock(run_log.wrap(fn))``.

    That order matters: reversed, a run blocked by a peer would emit
    start/skip/end instead of a single skip.
    """
    registry = JOB_REGISTRY if registry is None else registry
    jobs: dict[str, Callable] = {}
    for name, spec in registry.items():
        # The registry key is the job's identity everywhere -- lock key,
        # scheduler job id and log records. Deriving any of them from
        # fn.__name__ splits that identity, and two entries sharing one
        # function would silently share one lock.
        # `or`, never `.get("lock_ttl", cfg.lock_ttl)`: an explicit
        # "lock_ttl": None must fall back too. Passing None through reaches a
        # SET with no expiry, and one killed process would then block that job
        # forever.
        ttl = spec.get("lock_ttl") or cfg.lock_ttl
        lock = make_job_lock(cfg, name, on_skip=_skip_recorder(run_log, name), ttl=ttl)
        jobs[name] = lock(run_log.wrap(spec["fn"], name))
    return jobs
