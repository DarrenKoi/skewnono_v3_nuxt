from back_dev_home.ebeam.hitachi.live_alarm.normalize import canonical_json, to_events


NOW = 1_000_000_000


def _row(**over):
    row = {
        "EQP_ID": "MCD101",
        "ALID": "9006",
        "UTC9": "2001-09-09 10:46:40",
        "ALARM_NAME": "Align Fail",
        "RECIPE_ID": "MONITOR/CD_TOP_01",
        "OPERATION_DESC": "CD MEASUREMENT",
        "LOT_TYPE_CD": "PROD",
    }
    row.update(over)
    return row


def test_every_documented_column_round_trips():
    event = to_events([_row()], now=NOW)[0]
    assert event["eqp_id"] == "MCD101"
    assert event["alid"] == "9006"
    assert event["kind"] == "align"
    assert event["alarm_name"] == "Align Fail"
    assert event["recipe_id"] == "MONITOR/CD_TOP_01"
    assert event["operation_desc"] == "CD MEASUREMENT"
    assert event["lot_type_cd"] == "PROD"
    assert event["id"] == f"MCD101|9006|{event['occurred_at']}"


def test_the_measurement_alid_maps_to_the_meas_kind():
    assert to_events([_row(ALID="9100")], now=NOW)[0]["kind"] == "meas"


def test_pandas_float_alid_is_normalized():
    # A DataFrame integer column reaches us as "9006.0"; both spellings are
    # the same alarm, and an unnormalized one has no kind and is dropped.
    assert to_events([_row(ALID="9006.0")], now=NOW)[0]["alid"] == "9006"


def test_nan_optional_fields_become_empty_not_the_text_nan():
    # DataFrame.to_dict leaves NaN in place. str(nan) is "nan", which would
    # render literally in the UI — the office-only null path home mocks never
    # produce.
    event = to_events(
        [_row(RECIPE_ID=float("nan"), OPERATION_DESC=None, LOT_TYPE_CD="NaT")],
        now=NOW,
    )[0]
    assert event["recipe_id"] == ""
    assert event["operation_desc"] == ""
    assert event["lot_type_cd"] == ""


def test_timestamp_is_the_fallback_for_utc9():
    row = _row()
    del row["UTC9"]
    row["TIMESTAMP"] = "2001-09-09 10:46:40"
    assert to_events([row], now=NOW)[0]["occurred_epoch"] > 0


def test_a_nan_utc9_falls_through_to_timestamp():
    # The fallback must survive a NaN, not just an absent key: a DataFrame
    # column that is null for one row still HAS the key.
    row = _row(UTC9=float("nan"))
    row["TIMESTAMP"] = "2001-09-09 10:46:40"
    assert to_events([row], now=NOW)[0]["occurred_epoch"] > 0


def test_unknown_alid_is_dropped():
    assert to_events([_row(ALID="1001")], now=NOW) == []


def test_undated_row_is_dropped():
    assert to_events([_row(UTC9="not a time")], now=NOW) == []


def test_far_future_row_is_dropped():
    # A fast upstream clock would otherwise park the event above the prune
    # boundary, where it never ages off the board.
    assert to_events([_row(UTC9="2035-01-01 00:00:00")], now=NOW) == []


def test_canonical_json_is_stable_regardless_of_key_order():
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})
