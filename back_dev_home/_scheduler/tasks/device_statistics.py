"""Weekly device-statistics snapshot: write, then sweep.

Thin call-throughs into ``device_statistics.data``, which dispatches to the
mock (disk) or office (MinIO) adapter. Both take no arguments because the
registry calls them with none -- retention is read from the environment here so
tuning it never requires a deploy.

Why the snapshot exists at all: the process-step source is a CURRENT-STATE
index, so "how many steps did this device have three weeks ago" cannot be
recovered by query. Filtering on chg_tm is not equivalent either -- any step
changed since the cutoff drops out entirely, so the further back you go the
more it under-counts. See docs/datatables/device_statistics_weekly_trend.txt.
"""

import logging
import os

from back_dev_home.ebeam.cdsem.device_statistics import data

logger = logging.getLogger("skewnono.scheduler")


def keep_weeks() -> int:
    """Retention, in weeks. The screen shows 8 (default ``points``); 12 leaves
    headroom if that is raised. Expected to change once the first snapshot's
    real size is known, so it is an env var rather than a constant."""
    try:
        return int(os.environ.get("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "").strip())
    except ValueError:
        return 12


def write_weekly_snapshot() -> str:
    location = data.write_weekly_snapshot()
    logger.info("weekly snapshot written to %s", location)
    return location


def sweep_weekly_snapshots() -> int:
    removed = data.sweep_weekly_snapshots(keep_weeks())
    logger.info("weekly snapshot sweep removed %d objects", removed)
    return removed
