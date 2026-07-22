from back_dev_home.ebeam.hitachi.live_alarm.writer.normalize import (
    canonical_json,
    to_events,
)


NOW = 1_784_768_400  # 2026-07-23 10:00:00 KST in Unix timestamp


def _row(alid="9006", eqp_id="MXCD101", utc9="2026-07-23 10:00:00"):
    return {
        "EQP_ID": eqp_id,
        "ALID": alid,
        "ALARM_NAME": "Align Fail",
        "UTC9": utc9,
        "RECIPE_ID": "MONITOR/CD_TOP_01",
        "OPERATION_DESC": "CD MEASUREMENT",
        "LOT_TYPE_CD": "PROD",
    }


def test_maps_alid_to_kind():
    assert to_events([_row("9006")], now=NOW)[0]["kind"] == "align"
    assert to_events([_row("9100")], now=NOW)[0]["kind"] == "meas"


def test_drops_alarms_outside_the_two_target_alids():
    assert to_events([_row("1001")], now=NOW) == []


def test_tolerates_a_float_shaped_alid():
    # The in-house feed has been seen emitting "9006.0" via pandas.
    assert to_events([_row("9006.0")], now=NOW)[0]["kind"] == "align"


def test_builds_a_stable_id():
    event = to_events([_row()], now=NOW)[0]
    assert event["id"] == f"MXCD101|9006|{event['occurred_at']}"


def test_occurred_at_carries_an_explicit_offset():
    assert to_events([_row()], now=NOW)[0]["occurred_at"].endswith("+09:00")


def test_occurred_epoch_is_populated():
    assert isinstance(to_events([_row()], now=NOW)[0]["occurred_epoch"], int)


def test_drops_events_dated_far_in_the_future():
    # An upstream clock running fast would otherwise park an event above
    # the pruning boundary forever.
    far = "2099-01-01 00:00:00"
    assert to_events([_row(utc9=far)], now=NOW) == []


def test_drops_rows_with_an_unparseable_timestamp():
    assert to_events([_row(utc9="not a date")], now=NOW) == []


def test_canonical_json_is_key_order_independent():
    # ZSET dedupe is by exact member string, so serialization must be stable.
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert canonical_json(a) == canonical_json(b)


def test_canonical_json_has_no_incidental_whitespace():
    assert " " not in canonical_json({"a": 1, "b": 2})
