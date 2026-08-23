"""normalize.to_events is the ONLY place that knows the office column names.

Everything downstream — the ZSET member, board.py, the Vue row — speaks the
snake_case contract, so these tests are what pin the mapping. The row literals
below are spelled exactly as the office DataFrame spells them (all-caps names,
per docs/datatables/hitachi/live_alarm_board.txt); a test that used friendly names
would pass while the real feed produced a board of blanks.
"""

import pandas as pd

from back_dev_home.ebeam.live_alarm.contracts import ALID_KIND
from back_dev_home.ebeam.live_alarm.normalize import canonical_json, to_events


NOW = 1_000_000_000


def _row(**over):
    row = {
        "UTC9": "2001-09-09 10:46:40",
        "RAWID": 881423,
        "EQP_ID": "MCD101",
        "LOT_ID": "NX4201.1",
        "RECIPE_ID": "MONITOR/CD_TOP_01",
        "OPERATION_DESC": "CD MEASUREMENT",
        "ALID": "9006",
        "AL_CODE": "C06",
        "AL_TEXT": "ALIGNMENT FAIL",
        "AL_TYPE": "warning",
        "LOT_TYPE_CD": "PROD",
        "CASSETTE_ID": "FOUP103",
        "PPID": "MONITOR/CD_TOP_01.rcp",
        "STEP_ID": "1004",
        "MESEVENTNAME": "waferload",
        "ALARM_MODELNAME": "CG6300",
        "EQ_STAT": "proc",
        "TIMESTAMP": "2001-09-09T10:46:40",
    }
    row.update(over)
    return row


def test_every_documented_column_round_trips():
    event = to_events([_row()], now=NOW)[0]
    assert event["rawid"] == "881423"
    assert event["eqp_id"] == "MCD101"
    assert event["alarm_modelname"] == "CG6300"
    assert event["alid"] == "9006"
    assert event["al_code"] == "C06"
    assert event["al_type"] == "warning"
    assert event["kind"] == "align"
    assert event["alarm_name"] == "ALIGNMENT FAIL"
    assert event["lot_id"] == "NX4201.1"
    assert event["cassette_id"] == "FOUP103"
    assert event["recipe_id"] == "MONITOR/CD_TOP_01"
    assert event["ppid"] == "MONITOR/CD_TOP_01.rcp"
    assert event["operation_desc"] == "CD MEASUREMENT"
    assert event["step_id"] == "1004"
    assert event["lot_type_cd"] == "PROD"
    assert event["meseventname"] == "waferload"
    assert event["eq_stat"] == "proc"


def test_the_measurement_alids_map_to_the_meas_kind():
    # Two ids, one kind: the UI groups and counts by kind, and says which
    # failure it was with alid/alarm_name. A mapping that collapsed these to
    # separate kinds would split one meaningful counter into two.
    assert to_events([_row(ALID="9007")], now=NOW)[0]["kind"] == "meas"
    assert to_events([_row(ALID="9035")], now=NOW)[0]["kind"] == "meas"


def test_every_alid_in_the_contract_survives_normalization():
    # Guards the direction the individual tests above cannot: an id added to
    # ALID_KIND but not actually reachable through to_events would render an
    # empty board for that alarm and look like a quiet fab.
    for alid, kind in ALID_KIND.items():
        events = to_events([_row(ALID=alid)], now=NOW)
        assert len(events) == 1, f"alid {alid} in ALID_KIND was dropped"
        assert events[0]["kind"] == kind


def test_rawid_is_the_event_id():
    # RAWID is the feed's own unique key, so it dedupes exactly.
    assert to_events([_row()], now=NOW)[0]["id"] == "881423"


def test_two_alarms_from_one_tool_in_one_second_stay_two_rows():
    # The reason the id is RAWID and not the composite: these two share
    # eqp_id, alid AND second, so the old "{eqp}|{alid}|{at}" key collapsed
    # them into one row and silently lost an alarm.
    events = to_events([_row(RAWID=1), _row(RAWID=2)], now=NOW)
    assert {e["id"] for e in events} == {"1", "2"}


def test_a_feed_without_rawid_falls_back_to_the_composite_id():
    row = _row()
    del row["RAWID"]
    event = to_events([row], now=NOW)[0]
    assert event["rawid"] == ""
    assert event["id"] == f"MCD101|9006|{event['occurred_at']}"


def test_pandas_float_ints_are_normalized():
    # One null anywhere in an integer column promotes the whole column to
    # float, so every value arrives with a ".0" tail. An unnormalized alid has
    # no kind and is dropped; an unnormalized rawid dedupes against nothing.
    event = to_events([_row(ALID="9006.0", RAWID="881423.0")], now=NOW)[0]
    assert event["alid"] == "9006"
    assert event["rawid"] == "881423"


def test_nan_optional_fields_become_empty_not_the_text_nan():
    # DataFrame.to_dict leaves NaN in place. str(nan) is "nan", which would
    # render literally in the UI — the office-only null path home mocks never
    # produce.
    event = to_events(
        [_row(RECIPE_ID=float("nan"), OPERATION_DESC=None, LOT_TYPE_CD="NaT",
              CASSETTE_ID=float("nan"), PPID=None, EQ_STAT="None")],
        now=NOW,
    )[0]
    assert event["recipe_id"] == ""
    assert event["operation_desc"] == ""
    assert event["lot_type_cd"] == ""
    assert event["cassette_id"] == ""
    assert event["ppid"] == ""
    assert event["eq_stat"] == ""


def test_a_real_dataframe_row_round_trips():
    # The office hands us `df.to_dict(orient="records")`, not literals: UTC9 is
    # datetime64[us] and arrives as a Timestamp, RAWID as a numpy int. Neither
    # is a str, and both used to be exercised only in production.
    frame = pd.DataFrame([_row()]).astype({"UTC9": "datetime64[us]", "RAWID": "int64"})
    event = to_events(frame.to_dict(orient="records"), now=NOW)[0]
    assert event["rawid"] == "881423"
    assert event["occurred_at"] == "2001-09-09 10:46:40+09:00"


def test_a_sub_second_utc9_is_kept_not_dropped():
    # datetime64[us] str()s with microseconds. The two strptime formats this
    # replaced matched neither, so such a row was discarded as undated.
    assert to_events([_row(UTC9="2001-09-09 10:46:40.123456")], now=NOW)[0]["occurred_epoch"] > 0


def test_timestamps_without_an_offset_are_read_as_kst():
    # Both columns are already 한국 시간, so attaching +09:00 relabels rather
    # than shifts. Reading them as UTC would put every alarm 9 hours in the
    # past and off the 20-minute board entirely.
    assert to_events([_row()], now=NOW)[0]["occurred_at"] == "2001-09-09 10:46:40+09:00"


def test_timestamp_is_the_fallback_for_utc9():
    row = _row()
    del row["UTC9"]
    assert to_events([row], now=NOW)[0]["occurred_epoch"] > 0


def test_a_nan_utc9_falls_through_to_timestamp():
    # The fallback must survive a NaN, not just an absent key: a DataFrame
    # column that is null for one row still HAS the key.
    assert to_events([_row(UTC9=float("nan"))], now=NOW)[0]["occurred_epoch"] > 0


def test_al_text_wins_over_the_legacy_alarm_name():
    row = _row(ALARM_NAME="Align Fail")
    assert to_events([row], now=NOW)[0]["alarm_name"] == "ALIGNMENT FAIL"


def test_alarm_name_is_the_fallback_for_a_feed_without_al_text():
    row = _row(ALARM_NAME="Align Fail")
    del row["AL_TEXT"]
    assert to_events([row], now=NOW)[0]["alarm_name"] == "Align Fail"


def test_unknown_columns_are_ignored():
    # The real DataFrame carries more columns than we map. Reading by name
    # means extra ones are inert rather than a schema error.
    event = to_events([_row(SOME_OTHER_COLUMN="x", AND_ANOTHER=7)], now=NOW)[0]
    assert "SOME_OTHER_COLUMN" not in event


def test_unknown_alid_is_dropped():
    assert to_events([_row(ALID="1001")], now=NOW) == []


def test_the_retired_9100_is_no_longer_rendered():
    # 9100 came from the POC's separate get_measurement_fail_alarms() and does
    # not exist in the unified feed; 9007/9035 replaced it.
    assert to_events([_row(ALID="9100")], now=NOW) == []


def test_undated_row_is_dropped():
    assert to_events([_row(UTC9="not a time", TIMESTAMP="")], now=NOW) == []


def test_far_future_row_is_dropped():
    # A fast upstream clock would otherwise park the event above the prune
    # boundary, where it never ages off the board.
    assert to_events([_row(UTC9="2035-01-01 00:00:00", TIMESTAMP="")], now=NOW) == []


def test_canonical_json_is_stable_regardless_of_key_order():
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})
