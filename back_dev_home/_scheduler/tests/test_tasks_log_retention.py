import os
import time

import pytest

from back_dev_home._scheduler.tasks.log_retention import (
    DEFAULT_PATTERNS,
    LogRetentionConfig,
    load_config,
    purge_old_logs,
)

DAY = 86400
NOW = 1_754_000_000.0  # fixed clock; nothing here may depend on the real one


@pytest.fixture
def logdir(tmp_path):
    return tmp_path / "logs"


def _write(directory, name: str, age_days: float):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("x")
    stamp = NOW - age_days * DAY
    os.utime(path, (stamp, stamp))
    return path


def _cfg(directory, **kw) -> LogRetentionConfig:
    return LogRetentionConfig(directory=directory, **kw)


def test_files_older_than_the_window_are_removed(logdir):
    old = _write(logdir, "uwsgi-2026-07-20.log", age_days=9)
    assert purge_old_logs(_cfg(logdir), now=NOW) == 1
    assert not old.exists()


def test_files_inside_the_window_are_kept(logdir):
    fresh = _write(logdir, "uwsgi-2026-08-04.log", age_days=1)
    edge = _write(logdir, "uwsgi-2026-07-30.log", age_days=6.9)
    assert purge_old_logs(_cfg(logdir), now=NOW) == 0
    assert fresh.exists() and edge.exists()


def test_the_file_being_written_right_now_is_never_a_candidate(logdir):
    # The mtime of today's uWSGI log is seconds old, so this is really a
    # statement about the cutoff arithmetic having the right sign.
    today = _write(logdir, "uwsgi-2026-08-05.log", age_days=0)
    purge_old_logs(_cfg(logdir), now=NOW)
    assert today.exists()


def test_non_matching_names_are_left_alone(logdir):
    keep = _write(logdir, "important.txt", age_days=90)
    _write(logdir, "uwsgi-old.log", age_days=90)
    assert purge_old_logs(_cfg(logdir), now=NOW) == 1
    assert keep.exists()


def test_rotated_suffixes_match_the_default_patterns(logdir):
    rotated = _write(logdir, "uwsgi.log.1", age_days=30)
    assert purge_old_logs(_cfg(logdir), now=NOW) == 1
    assert not rotated.exists()


def test_subdirectories_are_never_walked(logdir):
    nested = _write(logdir / "archive", "uwsgi-2026-01-01.log", age_days=200)
    # The directory itself is old too, and matches nothing -- but a recursive
    # implementation would still reach the file inside it.
    assert purge_old_logs(_cfg(logdir), now=NOW) == 0
    assert nested.exists()


def test_a_symlink_is_skipped_rather_than_followed(logdir, tmp_path):
    outsider = _write(tmp_path / "elsewhere", "uwsgi-2026-01-01.log", age_days=200)
    logdir.mkdir(parents=True, exist_ok=True)
    link = logdir / "current.log"
    link.symlink_to(outsider)
    assert purge_old_logs(_cfg(logdir), now=NOW) == 0
    assert outsider.exists()
    assert link.is_symlink()


def test_a_missing_directory_is_reported_not_raised(tmp_path):
    assert purge_old_logs(_cfg(tmp_path / "nope"), now=NOW) == 0


def test_a_non_positive_retention_deletes_nothing(logdir):
    # 0 would mean "delete the file uWSGI has open"; only a mis-set env var
    # can produce it, so the job refuses rather than obeys.
    old = _write(logdir, "uwsgi-2026-01-01.log", age_days=200)
    assert purge_old_logs(_cfg(logdir, retention_days=0), now=NOW) == 0
    assert purge_old_logs(_cfg(logdir, retention_days=-7), now=NOW) == 0
    assert old.exists()


def test_a_second_run_is_a_no_op(logdir):
    _write(logdir, "uwsgi-2026-01-01.log", age_days=200)
    assert purge_old_logs(_cfg(logdir), now=NOW) == 1
    assert purge_old_logs(_cfg(logdir), now=NOW) == 0


def test_one_undeletable_file_does_not_abandon_the_sweep(logdir, monkeypatch):
    _write(logdir, "uwsgi-2026-01-01.log", age_days=200)
    _write(logdir, "uwsgi-2026-01-02.log", age_days=200)
    real_unlink = type(logdir).unlink
    calls = {"n": 0}

    def flaky(self, *a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError("nope")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(type(logdir), "unlink", flaky)
    assert purge_old_logs(_cfg(logdir), now=NOW) == 1


# ── config ─────────────────────────────────────────────────────────────────


def test_the_default_directory_is_the_deploy_log_folder():
    cfg = load_config({})
    assert cfg.directory.name == "logs"
    assert cfg.retention_days == 7
    assert cfg.patterns == DEFAULT_PATTERNS


def test_env_overrides_reach_the_config():
    cfg = load_config(
        {
            "SKEWNONO_LOG_DIR": "/var/log/skewnono",
            "SKEWNONO_LOG_RETENTION_DAYS": "14",
            "SKEWNONO_LOG_GLOB": "*.log, uwsgi-*",
        }
    )
    assert str(cfg.directory) == "/var/log/skewnono"
    assert cfg.retention_days == 14
    assert cfg.patterns == ("*.log", "uwsgi-*")


def test_a_garbage_retention_falls_back_to_the_default():
    # Falling back to 7 rather than to int()'s failure: a typo must not read
    # as 0, which the sweep would treat as "delete everything".
    assert load_config({"SKEWNONO_LOG_RETENTION_DAYS": "seven"}).retention_days == 7


def test_the_default_window_is_a_week_of_real_seconds(logdir):
    # Guards the unit of the cutoff arithmetic against a days/hours slip.
    _write(logdir, "a.log", age_days=7.5)
    _write(logdir, "b.log", age_days=6.5)
    assert purge_old_logs(_cfg(logdir), now=NOW) == 1
    assert (logdir / "b.log").exists()


def test_the_clock_defaults_to_now(logdir):
    stale = logdir / "stale.log"
    logdir.mkdir(parents=True, exist_ok=True)
    stale.write_text("x")
    long_ago = time.time() - 30 * DAY
    os.utime(stale, (long_ago, long_ago))
    assert purge_old_logs(_cfg(logdir)) == 1
