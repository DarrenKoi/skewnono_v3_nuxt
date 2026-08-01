"""What runs, when, and with which knobs.

Four knobs matter, and for jobs measured in minutes the last two matter most.

``minute=``  Cron fires at an exact instant, so two jobs written ``minute=0``
             start TOGETHER, not "around" the hour. Every job gets its own
             slot; a test asserts no two share one.

``lock_ttl`` Orphan-clear window only -- a live run re-arms its own TTL, so it
             may overrun this freely. Smaller is better: it bounds how long a
             lock left by a killed process blocks the job. All three jobs are
             daily or weekly, so any value under a day skips zero runs. Do NOT
             reason "weekly job, weekly TTL" -- that is this knob's most common
             mistake.

``misfire_grace_time``  How late a start may be and still happen. Checked when
             the job reaches a worker thread, so it covers queue wait. The 60s
             APScheduler default is far too tight for a WEEKLY job: a missed
             snapshot write does not retry until next Monday, so six hours of
             grace costs nothing and saves a week.

Hours all sit inside 01:00-08:00, the confirmed quiet window (user-confirmed
2026-08-01), and the sweep deliberately follows the write.
"""

from collections.abc import Callable

from apscheduler.triggers.cron import CronTrigger

from back_dev_home._scheduler.locks import make_job_lock
from back_dev_home._scheduler.tasks.device_statistics import (
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)
from back_dev_home._scheduler.tasks.image_cache import purge_image_cache

JOB_REGISTRY: dict[str, dict] = {
    "image_cache_purge": {
        "fn": purge_image_cache,
        # Nightly. :10 keeps it clear of the two weekly slots below.
        "trigger": CronTrigger(hour=3, minute=10),
        "lock_ttl": 600,
        "misfire_grace_time": 3600,
    },
    "weekly_snapshot_write": {
        "fn": write_weekly_snapshot,
        # Monday, because the snapshot key IS that week's Monday.
        "trigger": CronTrigger(day_of_week="mon", hour=1, minute=0),
        "lock_ttl": 600,
        # Six hours: the next retry would otherwise be next Monday.
        "misfire_grace_time": 21600,
    },
    "weekly_snapshot_sweep": {
        "fn": sweep_weekly_snapshots,
        # 90 minutes after the write, never before: sweeping first could delete
        # the oldest kept snapshot in the same hour the newest arrives, and a
        # failed write would still trigger deletions.
        "trigger": CronTrigger(day_of_week="mon", hour=2, minute=30),
        "lock_ttl": 600,
        "misfire_grace_time": 3600,
    },
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
        lock = make_job_lock(cfg, name, on_skip=_skip_recorder(run_log, name))
        jobs[name] = lock(run_log.wrap(spec["fn"], name))
    return jobs
