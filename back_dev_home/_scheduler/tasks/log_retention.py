"""Nightly log-file retention sweep.

uWSGI writes one file per day into the deploy's ``logs/`` directory
(``/project/workSpace/logs/uwsgi-2026-08-03.log``). Nothing rotates them away,
so the directory grows without bound on a host we do not administer. This job
keeps the last ``SKEWNONO_LOG_RETENTION_DAYS`` days (default 7) and deletes the
rest.

**Age is mtime, not the date in the file name.** A day-stamped file stops being
written the moment its day ends, so its mtime already *is* its date -- and mtime
keeps working for any other log the deploy grows later, including rotated
``.log.1`` files whose name carries no date at all. The one case the two
disagree on is a file copied or restored into the directory: that resets mtime,
and the sweep then keeps it a further week. Keeping a file too long is the safe
direction of that error.

Scope is deliberately narrow, because this job deletes things:

* one directory, never a recursive walk -- a nested directory is somebody
  else's, and this job must not discover it;
* only names matching ``SKEWNONO_LOG_GLOB`` (default ``*.log``, ``*.log.*``);
* regular files only; symlinks are skipped rather than followed, so a link
  pointing outside the log directory can never make this unlink a stranger.

A per-file ``OSError`` (permissions, a file vanishing under us) is logged and
skipped -- one undeletable file must not abandon the rest of the sweep.
"""

import logging
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from back_dev_home._runtime.env import project_root

logger = logging.getLogger("skewnono.scheduler")

DEFAULT_RETENTION_DAYS = 7
DEFAULT_PATTERNS = ("*.log", "*.log.*")
_SECONDS_PER_DAY = 86400


@dataclass(frozen=True)
class LogRetentionConfig:
    directory: Path
    retention_days: int = DEFAULT_RETENTION_DAYS
    patterns: tuple[str, ...] = DEFAULT_PATTERNS


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    """Same fallback-on-garbage rule as ``_scheduler/config.py``.

    A typo'd retention must not raise -- but note it also must not be read as
    0, which is why the parse failure returns the default rather than int()'s
    partial result.
    """
    try:
        return int(env.get(key, "").strip())
    except ValueError:
        return default


def load_config(env: Mapping[str, str] | None = None) -> LogRetentionConfig:
    """Env-driven, with the deploy layout as the default.

    ``project_root()`` is ``/project/workSpace`` on the cloud (that path is a
    filesystem fact, see ``_runtime/env.py``), so the default resolves to the
    real log directory there with nothing set, and to a usually-absent
    ``logs/`` at home -- which the sweep reports and skips.
    """
    env = os.environ if env is None else env
    raw_dir = (env.get("SKEWNONO_LOG_DIR") or "").strip()
    directory = Path(raw_dir) if raw_dir else project_root() / "logs"
    raw_glob = (env.get("SKEWNONO_LOG_GLOB") or "").strip()
    patterns = (
        tuple(p.strip() for p in raw_glob.split(",") if p.strip())
        if raw_glob
        else DEFAULT_PATTERNS
    )
    return LogRetentionConfig(
        directory=directory,
        retention_days=_int(
            env, "SKEWNONO_LOG_RETENTION_DAYS", DEFAULT_RETENTION_DAYS
        ),
        patterns=patterns or DEFAULT_PATTERNS,
    )


def purge_old_logs(
    cfg: LogRetentionConfig | None = None, now: float | None = None
) -> int:
    """Delete matching log files older than the retention window.

    Returns the number of files removed. Idempotent: a second run in the same
    minute finds nothing left to delete.
    """
    cfg = cfg or load_config()
    if cfg.retention_days <= 0:
        # 0 would mean "delete everything, including the file uWSGI has open
        # right now". Refuse rather than obey -- the only way to get here is a
        # mis-set env var.
        logger.warning(
            "log_retention disabled: retention_days=%d is not positive",
            cfg.retention_days,
        )
        return 0
    if not cfg.directory.is_dir():
        logger.info("log_retention: %s is not a directory; nothing to sweep",
                    cfg.directory)
        return 0

    cutoff = (time.time() if now is None else now) - cfg.retention_days * _SECONDS_PER_DAY
    removed = 0
    for path in sorted(_candidates(cfg)):
        try:
            # is_symlink() first, and it must stay first: is_file() follows
            # the link, so a link aimed outside the log directory would
            # otherwise pass the check and get unlinked on its target's age.
            if path.is_symlink() or not path.is_file():
                continue
            if path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
        except OSError as exc:
            logger.warning("log_retention could not remove %s: %s", path, exc)
            continue
        removed += 1
        logger.info("log_retention removed %s", path.name)

    logger.info(
        "log_retention removed %d file(s) older than %d day(s) from %s",
        removed,
        cfg.retention_days,
        cfg.directory,
    )
    return removed


def _candidates(cfg: LogRetentionConfig) -> set[Path]:
    """Non-recursive glob union.

    A set because the default patterns overlap on nothing today but would the
    moment someone adds ``*``-ish patterns -- and unlinking the same path twice
    turns a normal sweep into a spurious warning.
    """
    return {p for pattern in cfg.patterns for p in cfg.directory.glob(pattern)}
