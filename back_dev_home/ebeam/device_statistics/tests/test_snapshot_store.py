import json

from back_dev_home.ebeam.device_statistics.data import get_weekly_trend_data
from back_dev_home.ebeam.device_statistics.providers.snapshot_store import (
    build_weekly_snapshot,
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)

BUCKETS = ("all", "only_normal", "mother_normal", "only_sample")


def test_payload_has_the_documented_shape():
    payload = build_weekly_snapshot()
    assert set(payload) == {"date", "generated_at", "summaries"}
    assert set(payload["summaries"]) == set(BUCKETS)
    assert payload["generated_at"].endswith("+09:00")


def test_payload_carries_summaries_but_not_recipe_info():
    # Snapshots are summary-only by design: device x bucket x recipe would be
    # GB-scale weekly, and no screen reads it (docs/datatables/
    # device_statistics_weekly_trend.txt).
    payload = build_weekly_snapshot()
    assert payload["summaries"]["all"], "expected at least one summary row"
    assert "all_rcp_info" not in payload["summaries"]


def test_default_date_is_a_monday():
    from datetime import date

    payload = build_weekly_snapshot()
    assert date.fromisoformat(payload["date"]).weekday() == 0


def test_default_date_matches_a_week_the_trend_returns():
    # The mock anchors weeks on BASE_TIME, not today. A snapshot named for a
    # week the trend never returns would be unreadable by construction.
    payload = build_weekly_snapshot()
    # Only the date keys matter here, not which lots are in them, so a single
    # lot avoids the ~4.6s/week cost of computing all 4000 lots x 8 weeks.
    from back_dev_home.ebeam.device_statistics.providers.statistics import (
        _lot_index,
    )
    one_lot = [next(iter(_lot_index()))]
    assert payload["date"] in get_weekly_trend_data(one_lot, points=8)


def test_write_then_read_back_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    path = write_weekly_snapshot("2026-06-01")
    written = json.loads((tmp_path / "2026-06-01.json").read_text(encoding="utf-8"))
    assert written["date"] == "2026-06-01"
    assert set(written["summaries"]) == set(BUCKETS)
    assert path.endswith("2026-06-01.json")


def test_rewriting_the_same_week_overwrites(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    write_weekly_snapshot("2026-06-01")
    write_weekly_snapshot("2026-06-01")
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_sweep_keeps_the_newest_and_deletes_by_key_date(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    for week in ("2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25"):
        write_weekly_snapshot(week)

    assert sweep_weekly_snapshots(keep_weeks=2) == 2
    remaining = sorted(p.stem for p in tmp_path.glob("*.json"))
    assert remaining == ["2026-05-18", "2026-05-25"]


def test_sweep_ignores_files_that_are_not_dated_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    write_weekly_snapshot("2026-05-04")
    (tmp_path / "notes.json").write_text("{}", encoding="utf-8")

    sweep_weekly_snapshots(keep_weeks=0)
    assert (tmp_path / "notes.json").exists()


def test_sweep_on_a_missing_directory_is_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path / "nope"))
    assert sweep_weekly_snapshots(keep_weeks=12) == 0


def test_trend_still_returns_every_week_with_no_snapshots(tmp_path, monkeypatch):
    # REGRESSION GUARD. The office adapter omits past weeks that have no
    # snapshot. If that rule ever leaks into the mock, a fresh checkout returns
    # 1 date instead of 8 and the trend chart goes blank until eight Mondays
    # have physically passed. The mock computes every week live, on purpose.
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    # Only the count of date keys is asserted, not lot content, so a single
    # lot avoids the ~4.6s/week cost of computing all 4000 lots x 8 weeks.
    from back_dev_home.ebeam.device_statistics.providers.statistics import (
        _lot_index,
    )
    one_lot = [next(iter(_lot_index()))]
    assert len(get_weekly_trend_data(one_lot, points=8)) == 8
