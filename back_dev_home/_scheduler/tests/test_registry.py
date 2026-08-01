import pytest
from flask import Flask

from back_dev_home._scheduler import start_scheduler
from back_dev_home._scheduler.config import load_scheduler_config
from back_dev_home._scheduler.registry import JOB_REGISTRY, build_jobs, build_schedule
from back_dev_home._scheduler.runlog import MemoryRunLog


CFG = load_scheduler_config({})


@pytest.fixture
def triggers(monkeypatch):
    """Triggers built from the SHIPPED defaults, not from the ambient .env.

    `build_schedule` resolves the purge hour through msr_image's config, so
    without clearing IMAGE_CACHE_PURGE_HOUR these assertions would read whatever
    the developer's (or the office's) .env happens to set. A .env moving the
    purge outside 01:00-08:00 would then fail the quiet-window test on a
    perfectly valid setting -- a failure about config, dressed up as a failure
    about the registry. `test_the_purge_hour_env_var_is_honored` covers the
    override path deliberately; these cover the defaults.
    """
    monkeypatch.delenv("IMAGE_CACHE_PURGE_HOUR", raising=False)
    return build_schedule(CFG)


def _field(trigger, name: str) -> str:
    return str(next(f for f in trigger.fields if f.name == name))


def test_every_entry_has_a_function_and_a_trigger(triggers):
    for name, spec in JOB_REGISTRY.items():
        assert callable(spec["fn"]), f"{name} has no callable fn"
        assert callable(spec.get("cron")), f"{name} has no cron field factory"
        assert isinstance(spec.get("lock_ttl"), int), f"{name} has no lock_ttl"
        assert name in triggers, f"{name} builds no trigger"


def test_all_three_jobs_are_registered():
    assert set(JOB_REGISTRY) == {
        "image_cache_purge",
        "weekly_snapshot_write",
        "weekly_snapshot_sweep",
    }


def test_no_two_jobs_share_a_fire_instant(triggers):
    # Cron fires at an exact instant, so two jobs written minute=0 start
    # TOGETHER, not "around" the hour.
    slots = []
    for name, trigger in triggers.items():
        fields = {f.name: str(f) for f in trigger.fields}
        slots.append(
            (fields.get("day_of_week"), fields.get("hour"), fields.get("minute"))
        )
    assert len(set(slots)) == len(slots), f"two jobs share a fire instant: {slots}"


def test_every_job_fires_inside_the_quiet_window(triggers):
    # 01:00-08:00 is the confirmed quiet window (user-confirmed 2026-08-01).
    for name, trigger in triggers.items():
        hour = int(_field(trigger, "hour"))
        assert 1 <= hour < 8, f"{name} fires at {hour}, outside the quiet window"


def test_the_sweep_runs_after_the_write(triggers):
    # Sweeping first would race the write and could delete the oldest kept
    # snapshot in the same hour the newest arrives.
    def hour(name):
        return int(_field(triggers[name], "hour"))

    assert hour("weekly_snapshot_sweep") > hour("weekly_snapshot_write")


def test_build_jobs_returns_one_callable_per_entry(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    jobs = build_jobs(load_scheduler_config({}), MemoryRunLog(10))
    assert set(jobs) == set(JOB_REGISTRY)
    assert all(callable(fn) for fn in jobs.values())


def test_wrapped_job_records_start_and_end(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    run_log = MemoryRunLog(10)
    cfg = load_scheduler_config({})
    registry = {"noop": {"fn": lambda: 1, "cron": dict, "lock_ttl": 60}}
    jobs = build_jobs(cfg, run_log, registry=registry)
    jobs["noop"]()
    assert [r["event"] for r in run_log.read(10)] == ["end", "start"]


def test_testing_app_starts_no_scheduler():
    app = Flask(__name__)
    app.testing = True
    assert start_scheduler(app) is None


def test_starting_twice_returns_the_same_scheduler(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    # conftest.py sets this to "0" for the whole session; undo it here since
    # this test needs a real scheduler to start.
    monkeypatch.delenv("SKEWNONO_SCHEDULER_ENABLED", raising=False)
    app = Flask(__name__)
    app.debug = False
    first = start_scheduler(app)
    try:
        assert first is not None
        assert start_scheduler(app) is first
        assert len(first.get_jobs()) == len(JOB_REGISTRY)
    finally:
        if first is not None:
            first.shutdown(wait=False)


def test_disabled_by_env_starts_no_scheduler(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.setenv("SKEWNONO_SCHEDULER_ENABLED", "0")
    app = Flask(__name__)
    app.debug = False
    assert start_scheduler(app) is None
    assert "scheduler" not in app.extensions


def test_unset_env_still_starts_a_scheduler(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.delenv("SKEWNONO_SCHEDULER_ENABLED", raising=False)
    app = Flask(__name__)
    app.debug = False
    scheduler = start_scheduler(app)
    try:
        assert scheduler is not None
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


def test_start_exposes_the_run_log_on_the_app(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    # conftest.py sets this to "0" for the whole session; undo it here since
    # this test needs a real scheduler to start.
    monkeypatch.delenv("SKEWNONO_SCHEDULER_ENABLED", raising=False)
    app = Flask(__name__)
    app.debug = False
    scheduler = start_scheduler(app)
    try:
        assert app.extensions["scheduler_run_log"] is not None
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


# ── timezone, purge hour, per-job lock TTL ──────────────────────────────────


def test_every_trigger_carries_the_configured_timezone():
    # A CronTrigger built without timezone= binds get_localzone() for good, and
    # BackgroundScheduler(timezone=...) does NOT retag it. On a UTC cloud host
    # that put the "quiet window" jobs at 12:10 KST, mid-workday.
    cfg = load_scheduler_config({})
    for name, trigger in build_schedule(cfg).items():
        assert str(trigger.timezone) == cfg.timezone, (
            f"{name} fires in {trigger.timezone}, not {cfg.timezone}"
        )


def test_a_non_default_timezone_reaches_the_triggers():
    from dataclasses import replace

    cfg = replace(load_scheduler_config({}), timezone="UTC")
    for trigger in build_schedule(cfg).values():
        assert str(trigger.timezone) == "UTC"


def test_the_purge_hour_comes_from_the_image_cache_env_var(monkeypatch):
    # IMAGE_CACHE_PURGE_HOUR is documented in .env.example and
    # msr_image/MIGRATION.md (it coordinates with an Airflow DAG at 03:35 KST),
    # so the registry must read it rather than hardcode 3.
    monkeypatch.setenv("IMAGE_CACHE_PURGE_HOUR", "5")
    triggers = build_schedule(load_scheduler_config({}))
    assert _field(triggers["image_cache_purge"], "hour") == "5"
    assert _field(triggers["image_cache_purge"], "minute") == "10"


def test_the_purge_hour_defaults_to_three(monkeypatch):
    monkeypatch.delenv("IMAGE_CACHE_PURGE_HOUR", raising=False)
    triggers = build_schedule(load_scheduler_config({}))
    assert _field(triggers["image_cache_purge"], "hour") == "3"


def test_per_job_lock_ttl_reaches_the_lock(monkeypatch):
    seen = {}

    def fake_make_job_lock(cfg, job, on_skip=None, ttl=None):
        seen[job] = ttl
        return lambda fn: fn

    monkeypatch.setattr(
        "back_dev_home._scheduler.registry.make_job_lock", fake_make_job_lock
    )
    cfg = load_scheduler_config({})
    registry = {
        "per_job": {"fn": lambda: 1, "cron": dict, "lock_ttl": 42},
        "explicit_none": {"fn": lambda: 1, "cron": dict, "lock_ttl": None},
        "absent": {"fn": lambda: 1, "cron": dict},
    }
    build_jobs(cfg, MemoryRunLog(10), registry=registry)
    assert seen["per_job"] == 42
    # None and absent both fall back -- a None reaching the lock would SET the
    # key with no expiry, and one killed process would block the job forever.
    assert seen["explicit_none"] == cfg.lock_ttl
    assert seen["absent"] == cfg.lock_ttl
