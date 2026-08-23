"""Weekly device-statistics snapshot: write, then sweep.

Thin call-throughs into ``device_statistics.data``, which dispatches to the
mock (disk) or office (MinIO) adapter. Both take no arguments because the
registry calls them with none -- retention is read from the environment here so
tuning it never requires a deploy.

Why the snapshot exists at all: the process-step source is a CURRENT-STATE
index, so "how many steps did this device have three weeks ago" cannot be
recovered by query. Filtering on chg_tm is not equivalent either -- any step
changed since the cutoff drops out entirely, so the further back you go the
more it under-counts. See docs/datatables/hitachi/device_statistics_weekly_trend.txt.
"""

import logging
import os

from back_dev_home.ebeam.device_statistics import data

logger = logging.getLogger("skewnono.scheduler")


def keep_weeks() -> int:
    """Retention, in weeks. The requirement is six months of trend history
    (user-confirmed 2026-08-04), so the default is 26. It stays an env var so
    tuning after the first real snapshot's size is known never needs a deploy.

    Floored at 1. ``0`` and negatives parse cleanly through ``int()`` and would
    mean "delete every snapshot" -- and the snapshots are unrecoverable, since
    the source index only holds current state. Refusing an unsafe retention
    value rather than acting on it follows ``msr_image/cache.py``, which raises
    on an empty cache prefix for the same reason; here we clamp instead of
    raising because the scheduler must still run its other jobs.
    """
    try:
        weeks = int(os.environ.get("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "").strip())
    except ValueError:
        return 26
    if weeks < 1:
        logger.warning(
            "SKEWNONO_WEEKLY_TREND_KEEP_WEEKS=%d would delete every snapshot; "
            "clamping to 1", weeks,
        )
        return 1
    return weeks


def write_weekly_snapshot() -> str:
    location = data.write_weekly_snapshot()
    logger.info("weekly snapshot written to %s", location)
    return location


def sweep_weekly_snapshots() -> int:
    removed = data.sweep_weekly_snapshots(keep_weeks())
    logger.info("weekly snapshot sweep removed %d objects", removed)
    return removed
