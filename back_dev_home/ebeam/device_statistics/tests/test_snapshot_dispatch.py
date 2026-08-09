import inspect

from back_dev_home.ebeam.device_statistics import data
from back_dev_home.ebeam.device_statistics.providers import (
    mock,
    office_example,
)


def test_dispatcher_exports_both_snapshot_functions():
    assert "write_weekly_snapshot" in data.__all__
    assert "sweep_weekly_snapshots" in data.__all__


def test_dispatcher_reaches_the_mock_at_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    path = data.write_weekly_snapshot("2026-06-08")
    assert path.endswith("2026-06-08.json")
    assert data.sweep_weekly_snapshots(keep_weeks=0) == 1


def test_office_template_offers_the_same_two_functions():
    # The adapter is swapped in by copying office_example.py to office.py, so a
    # signature that drifts from the mock breaks only at the office.
    for name in ("write_weekly_snapshot", "sweep_weekly_snapshots"):
        assert hasattr(office_example, name), f"office_example is missing {name}"
        assert list(inspect.signature(getattr(mock, name)).parameters) == list(
            inspect.signature(getattr(office_example, name)).parameters
        ), f"{name} signature differs between mock and office"
