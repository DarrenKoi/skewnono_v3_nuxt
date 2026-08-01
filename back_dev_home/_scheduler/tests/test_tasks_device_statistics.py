from back_dev_home._scheduler.tasks.device_statistics import (
    keep_weeks,
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)


def test_both_tasks_take_no_arguments():
    import inspect

    assert list(inspect.signature(write_weekly_snapshot).parameters) == []
    assert list(inspect.signature(sweep_weekly_snapshots).parameters) == []


def test_keep_weeks_defaults_to_twelve(monkeypatch):
    monkeypatch.delenv("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", raising=False)
    assert keep_weeks() == 12


def test_keep_weeks_reads_the_env(monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "4")
    assert keep_weeks() == 4


def test_keep_weeks_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "soon")
    assert keep_weeks() == 12


def test_write_then_sweep_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "1")

    write_weekly_snapshot()
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert sweep_weekly_snapshots() == 0  # only one, and we keep one
