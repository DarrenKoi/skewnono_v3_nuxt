"""The reader: roster attribution, unmatched counting, and the three states.

Exercises _build_board directly so no Redis connection or office_utils import
is needed — get_board is a thin wrapper that supplies the client and index.
"""

from back_dev_home.ebeam.hitachi.live_alarm import refresh, roster
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


def _seed(client, *eqp_ids, now=NOW):
    """Put one align alarm per eqp_id on M16's board, stamped at `now`."""
    events = [
        {
            "id": f"{eqp}|9006|x", "eqp_id": eqp, "alid": "9006", "kind": "align",
            "alarm_name": "Align Fail", "occurred_at": "2001-09-09 10:46:40",
            "occurred_epoch": now - 60, "recipe_id": "", "operation_desc": "",
            "lot_type_cd": "",
        }
        for eqp in eqp_ids
    ]
    refresh._write_board(client, FAC, events, now)


def _board(client, tool_type="cd-sem", fab_name="M16A"):
    return reader._build_board(
        client, roster.build_index(ROWS), tool_type, fab_name, now=NOW
    )


def test_events_are_attributed_to_the_right_fab():
    client = FakeRedis()
    _seed(client, "MCD101", "MCD102")
    assert [e["eqp_id"] for e in _board(client, fab_name="M16A")["events"]] == ["MCD101"]
    assert [e["eqp_id"] for e in _board(client, fab_name="M16B")["events"]] == ["MCD102"]


def test_sibling_fabs_read_the_same_facility_board():
    # One office call filled this board; both fabs render from it.
    client = FakeRedis()
    _seed(client, "MCD101", "MCD102")
    assert _board(client, fab_name="M16A")["fetched_at"] is not None
    assert _board(client, fab_name="M16B")["fetched_at"] is not None


def test_events_are_attributed_to_the_right_tool_family():
    client = FakeRedis()
    _seed(client, "MCD101", "TP0421")
    assert [e["eqp_id"] for e in _board(client, "cd-sem", "M16A")["events"]] == ["MCD101"]
    assert [e["eqp_id"] for e in _board(client, "hv-sem", "M16A")["events"]] == ["TP0421"]


def test_unrostered_equipment_is_counted_not_shown():
    client = FakeRedis()
    _seed(client, "MCD101", "MCD999")
    result = _board(client)
    assert [e["eqp_id"] for e in result["events"]] == ["MCD101"]
    assert result["unmatched_count"] == 1


def test_a_sibling_fabs_alarm_is_not_counted_as_unmatched():
    # MCD102 is rostered, just not in M16A. That is a filter, not a gap —
    # counting it would make unmatched_count fire on every healthy board.
    client = FakeRedis()
    _seed(client, "MCD102")
    assert _board(client, fab_name="M16A")["unmatched_count"] == 0


def test_a_fab_with_no_tools_of_this_family_is_not_configured():
    result = reader._not_configured("hv-sem", "M16B", now=NOW)
    assert result["feed_status"] == "not_configured"
    assert result["events"] == []
    assert result["fetched_at"] is None
    assert result["unmatched_count"] == 0


def test_a_configured_fab_with_a_recent_fetch_is_live():
    client = FakeRedis()
    _seed(client, "MCD101")
    result = _board(client)
    assert result["feed_status"] == "live"
    assert result["fetched_at"] is not None


def test_an_old_fetch_reads_stale():
    client = FakeRedis()
    _seed(client, "MCD101", now=NOW - 5000)
    assert _board(client)["feed_status"] == "stale"


def test_events_outside_the_board_window_are_not_shown():
    client = FakeRedis()
    _seed(client, "MCD101", now=NOW - 5000)
    assert _board(client)["events"] == []


def test_covered_since_is_derived_from_the_board_window():
    client = FakeRedis()
    _seed(client, "MCD101")
    result = _board(client)
    assert result["covered_since"] is not None
    assert result["board_window_sec"] == BOARD_WINDOW_SEC


def test_newest_event_is_first():
    client = FakeRedis()
    events = [
        {
            "id": f"MCD101|9006|{n}", "eqp_id": "MCD101", "alid": "9006",
            "kind": "align", "alarm_name": "Align Fail",
            "occurred_at": "2001-09-09 10:46:40", "occurred_epoch": NOW - n,
            "recipe_id": "", "operation_desc": "", "lot_type_cd": "",
        }
        for n in (30, 10, 20)
    ]
    refresh._write_board(client, FAC, events, NOW)
    epochs = [e["occurred_epoch"] for e in _board(client)["events"]]
    assert epochs == sorted(epochs, reverse=True)
