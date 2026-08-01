"""The reader: roster attribution, unmatched counting, and the three states.

Exercises _build_board directly so no Redis connection is needed — get_board
is a thin wrapper that supplies the client, the cached index and the fetcher.
"""

import pytest

from back_dev_home.ebeam.hitachi.live_alarm import board, refresh, roster
from back_dev_home.ebeam.hitachi.live_alarm.contracts import BOARD_WINDOW_SEC
from back_dev_home.ebeam.hitachi.live_alarm.providers import office_example as reader
from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis


NOW = 1_000_000_000
FAC = "M16"

ROWS = [
    {"eqp_id": "MCD101", "fab_name": "M16A", "fac_id": "M16", "eqp_model_cd": "CG6300"},
    {"eqp_id": "MCD102", "fab_name": "M16B", "fac_id": "M16", "eqp_model_cd": "CG6300"},
    {"eqp_id": "TP0421", "fab_name": "M16A", "fac_id": "M16", "eqp_model_cd": "TP3000"},
]

INDEX = roster.build_index(ROWS)


def _event(eqp_id, epoch=NOW - 60):
    return {
        "id": f"{eqp_id}|9006|{epoch}", "eqp_id": eqp_id, "alid": "9006",
        "kind": "align", "alarm_name": "Align Fail",
        "occurred_at": "2001-09-09 10:46:40", "occurred_epoch": epoch,
        "recipe_id": "", "operation_desc": "", "lot_type_cd": "",
    }


def _seed(client, *events, now=NOW):
    """Write events onto M16's board, stamping fetched_at at `now`."""
    refresh._write_board(client, FAC, list(events), now)


def _board(client, tool_type="cd-sem", fab_name="M16A", now=NOW):
    return reader._build_board(
        client, INDEX, tool_type, fab_name, FAC,
        now=now, meta=refresh.read_meta(client, FAC),
    )


def test_events_are_attributed_to_the_right_fab():
    client = FakeRedis()
    _seed(client, _event("MCD101"), _event("MCD102"))
    assert [e["eqp_id"] for e in _board(client, fab_name="M16A")["events"]] == ["MCD101"]
    assert [e["eqp_id"] for e in _board(client, fab_name="M16B")["events"]] == ["MCD102"]


def test_sibling_fabs_read_the_same_facility_board():
    # One office call filled this board; both fabs render from it.
    client = FakeRedis()
    _seed(client, _event("MCD101"), _event("MCD102"))
    assert _board(client, fab_name="M16A")["fetched_at"] is not None
    assert _board(client, fab_name="M16B")["fetched_at"] is not None


def test_events_are_attributed_to_the_right_tool_family():
    client = FakeRedis()
    _seed(client, _event("MCD101"), _event("TP0421"))
    assert [e["eqp_id"] for e in _board(client, "cd-sem", "M16A")["events"]] == ["MCD101"]
    assert [e["eqp_id"] for e in _board(client, "hv-sem", "M16A")["events"]] == ["TP0421"]


def test_unrostered_equipment_is_counted_not_shown():
    client = FakeRedis()
    _seed(client, _event("MCD101"), _event("MCD999"))
    result = _board(client)
    assert [e["eqp_id"] for e in result["events"]] == ["MCD101"]
    assert result["unmatched_count"] == 1


def test_a_sibling_fabs_alarm_is_not_counted_as_unmatched():
    # MCD102 is rostered, just not in M16A. That is a filter, not a gap —
    # counting it would make unmatched_count fire on every healthy board.
    client = FakeRedis()
    _seed(client, _event("MCD102"))
    assert _board(client, fab_name="M16A")["unmatched_count"] == 0


def test_a_configured_fab_with_a_recent_fetch_is_live():
    client = FakeRedis()
    _seed(client, _event("MCD101"))
    result = _board(client)
    assert result["feed_status"] == "live"
    assert result["fetched_at"] is not None


def test_an_old_fetch_reads_stale():
    client = FakeRedis()
    _seed(client, _event("MCD101"), now=NOW - 5000)
    assert _board(client)["feed_status"] == "stale"


def test_events_outside_the_board_window_are_not_shown():
    client = FakeRedis()
    _seed(client, _event("MCD101", epoch=NOW - 5000), now=NOW - 5000)
    assert _board(client)["events"] == []


def test_covered_since_is_derived_from_the_board_window():
    client = FakeRedis()
    _seed(client, _event("MCD101"))
    result = _board(client)
    assert result["covered_since"] is not None
    assert result["board_window_sec"] == BOARD_WINDOW_SEC


def test_newest_event_is_first():
    client = FakeRedis()
    _seed(client, *(_event("MCD101", epoch=NOW - n) for n in (30, 10, 20)))
    epochs = [e["occurred_epoch"] for e in _board(client)["events"]]
    assert epochs == sorted(epochs, reverse=True)


# --------------------------------------------------------------------------
# get_board's guards, which run before any Redis or office work
# --------------------------------------------------------------------------


def test_a_fab_with_no_tools_of_this_family_is_not_configured():
    # M16B holds only a CD-SEM. Answered from the roster alone.
    result = board.payload(
        tool_type="hv-sem", fab_name="M16B", now=NOW, configured=False,
    )
    assert result["feed_status"] == "not_configured"
    assert result["events"] == []
    assert result["fetched_at"] is None
    assert result["covered_since"] is None
    assert result["unmatched_count"] == 0


def test_an_unconfigured_fab_never_reaches_redis_or_the_office(monkeypatch):
    # The roster answers first, so a typo'd fab costs neither a Redis
    # connection nor an office call.
    monkeypatch.setattr(reader, "_index", lambda: INDEX)
    monkeypatch.setattr(reader, "_office_fetch", _explode)
    monkeypatch.setattr(reader, "redis_client", _explode)
    assert reader.get_board("cd-sem", "ZZZ")["feed_status"] == "not_configured"


def test_missing_office_utils_raises_rather_than_serving_a_silent_empty_board():
    # office_utils is absent at home, so the real binding is exercised here.
    with pytest.raises(RuntimeError, match="office_utils"):
        reader._office_fetch()


def test_a_configured_fab_binds_the_office_fetch_before_touching_redis(monkeypatch):
    # A host missing office_utils must fail loudly, and must not have opened
    # a connection or taken a lock on the way out.
    monkeypatch.setattr(reader, "_index", lambda: INDEX)
    monkeypatch.setattr(reader, "redis_client", _explode)
    with pytest.raises(RuntimeError, match="office_utils"):
        reader.get_board("cd-sem", "M16A")


def _explode(*args, **kwargs):
    raise AssertionError("should not have been called")
