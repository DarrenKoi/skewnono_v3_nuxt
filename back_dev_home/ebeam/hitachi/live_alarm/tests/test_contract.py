"""Contract gate for live_alarm. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm
Office: SKEWNONO_LIVE_ALARM_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.live_alarm import data
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    ALID_KIND,
    AlarmEvent,
    LiveAlarmPayload,
)


def test_get_board_matches_contract():
    assert_matches(data.get_board("cd-sem", "R3"), LiveAlarmPayload)


def test_events_match_contract():
    board = data.get_board("cd-sem", "R3")
    assert isinstance(board["events"], list)
    for event in board["events"]:
        assert_matches(event, AlarmEvent)


def test_every_event_carries_a_known_kind():
    for event in data.get_board("cd-sem", "R3")["events"]:
        assert event["kind"] == ALID_KIND[event["alid"]]


def test_feed_status_is_one_of_three():
    assert data.get_board("cd-sem", "R3")["feed_status"] in {
        "live", "stale", "not_configured",
    }
