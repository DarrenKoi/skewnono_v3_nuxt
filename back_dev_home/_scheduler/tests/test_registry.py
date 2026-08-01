import pytest
from flask import Flask

from back_dev_home._scheduler import start_scheduler
from back_dev_home._scheduler.config import load_scheduler_config
from back_dev_home._scheduler.registry import JOB_REGISTRY, build_jobs
from back_dev_home._scheduler.runlog import MemoryRunLog


def test_every_entry_has_a_function_and_a_trigger():
    for name, spec in JOB_REGISTRY.items():
        assert callable(spec["fn"]), f"{name} has no callable fn"
        assert "trigger" in spec, f"{name} has no trigger"
        assert isinstance(spec.get("lock_ttl"), int), f"{name} has no lock_ttl"


def test_all_three_jobs_are_registered():
    assert set(JOB_REGISTRY) == {
        "image_cache_purge",
        "weekly_snapshot_write",
        "weekly_snapshot_sweep",
    }


def test_no_two_jobs_share_a_fire_instant():
    # Cron fires at an exact instant, so two jobs written minute=0 start
    # TOGETHER, not "around" the hour.
    slots = []
    for name, spec in JOB_REGISTRY.items():
        fields = {f.name: str(f) for f in spec["trigger"].fields}
        slots.append(
            (fields.get("day_of_week"), fields.get("hour"), fields.get("minute"))
        )
    assert len(set(slots)) == len(slots), f"two jobs share a fire instant: {slots}"


def test_every_job_fires_inside_the_quiet_window():
    # 01:00-08:00 is the confirmed quiet window (user-confirmed 2026-08-01).
    for name, spec in JOB_REGISTRY.items():
        hour = int(str(next(f for f in spec["trigger"].fields if f.name == "hour")))
        assert 1 <= hour < 8, f"{name} fires at {hour}, outside the quiet window"


def test_the_sweep_runs_after_the_write():
    # Sweeping first would race the write and could delete the oldest kept
    # snapshot in the same hour the newest arrives.
    def hour(name):
        spec = JOB_REGISTRY[name]
        return int(str(next(f for f in spec["trigger"].fields if f.name == "hour")))

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
    registry = {"noop": {"fn": lambda: 1, "trigger": None, "lock_ttl": 60}}
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
