import json

from backend.ebeam.device_statistics.data import get_weekly_trend_data
from backend.ebeam.device_statistics.providers.snapshot_store import (
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
    # GB-scale weekly, and no screen reads it (docs/datatables/hitachi/
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
    from backend.ebeam.device_statistics.providers.statistics import (
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
    from backend.ebeam.device_statistics.providers.statistics import (
        _lot_index,
    )
    one_lot = [next(iter(_lot_index()))]
    assert len(get_weekly_trend_data(one_lot, points=8)) == 8


def test_tool_type_axis_isolates_families(tmp_path, monkeypatch):
    """사무실 회신 2026-11-04 — 계열 축이 없으면 네 계열이 같은 파일을 덮어씁니다.

    CD-SEM 은 기존 자리(폴더 바로 아래), 계열은 ``<tool_type>/``. 각 sweep 은 자기
    폴더만 봅니다. 계열 summary 는 아직 없으므로 build 는 거절합니다.
    """
    import pytest

    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    write_weekly_snapshot("2026-05-04")
    hv = tmp_path / "hv-sem"
    hv.mkdir()
    for week in ("2026-05-11", "2026-05-18"):
        (hv / f"{week}.json").write_text("{}", encoding="utf-8")

    assert sweep_weekly_snapshots(keep_weeks=0) == 1          # CD-SEM 만
    assert sorted(p.stem for p in hv.glob("*.json")) == ["2026-05-11", "2026-05-18"]
    write_weekly_snapshot("2026-05-25")
    assert sweep_weekly_snapshots(keep_weeks=1, tool_type="hv-sem") == 1
    assert [p.stem for p in hv.glob("*.json")] == ["2026-05-18"]
    assert (tmp_path / "2026-05-25.json").exists()            # 계열 sweep 이 CD-SEM 을 안 지움

    with pytest.raises(NotImplementedError):
        write_weekly_snapshot("2026-05-25", tool_type="hv-sem")
    with pytest.raises(ValueError):
        sweep_weekly_snapshots(tool_type="../etc")


def test_office_sweep_does_not_mix_family_keys(monkeypatch):
    """office 템플릿의 MinIO sweep — 비재귀 나열이라 계열 하위 폴더가 섞이지 않습니다.

    재귀로 나열하면 전체 key 정렬에서 "hv-sem/..." 이 CD-SEM 주차 뒤에 와서
    CD-SEM 쪽이 지워집니다. 가짜 MinioObject 는 MinIO 의 비재귀 나열(직속 객체 +
    "/" 로 끝나는 폴더 항목)을 흉내 냅니다.
    """
    import minio_handler

    from backend.ebeam.device_statistics.providers import office_example

    base = office_example.MINIO_BASE
    keys = {f"{base}/2026-05-04.json", f"{base}/2026-05-11.json",
            f"{base}/hv-sem/2026-05-18.json", f"{base}/hv-sem/2026-05-25.json"}

    class _Obj:
        def __init__(self, name):
            self.object_name = name

    class FakeMinio:
        def list(self, prefix, recursive=True):
            names = set()
            for key in keys:
                if key.startswith(prefix):
                    rest = key[len(prefix):]
                    names.add(key if recursive or "/" not in rest
                              else prefix + rest.split("/", 1)[0] + "/")
            return [_Obj(n) for n in sorted(names)]

        def delete_matching(self, predicate, prefix=None):
            for key in [k for k in keys if predicate(k)]:
                keys.discard(key)
            return []

    monkeypatch.setattr(minio_handler, "MinioObject", FakeMinio)
    assert office_example.sweep_weekly_snapshots(keep_weeks=1) == 1
    assert keys == {f"{base}/2026-05-11.json",
                    f"{base}/hv-sem/2026-05-18.json", f"{base}/hv-sem/2026-05-25.json"}
    assert office_example.sweep_weekly_snapshots(keep_weeks=1, tool_type="hv-sem") == 1
    assert keys == {f"{base}/2026-05-11.json", f"{base}/hv-sem/2026-05-25.json"}
