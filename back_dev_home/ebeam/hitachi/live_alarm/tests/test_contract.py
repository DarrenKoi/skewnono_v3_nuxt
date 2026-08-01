"""Contract gate for live_alarm. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm
Office: SKEWNONO_LIVE_ALARM_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm

Both providers build the payload through the same pure `board` module, so the
three-empty-states model (live / stale / not_configured) and the alid->kind
table are shared law, asserted unfenced. What is NOT provider-independent is
the CONTENT of a configured fab's board: the mock derives a 0..3 event burst
from the current minute for a fixed fab whitelist, while the office reader
returns whatever the last successful office fetch put in Redis — which for a
healthy, quiet fab is legitimately nothing. Assumptions about the fab whitelist are
fenced behind get_data_provider("live_alarm") == "mock".

Note the event list can be empty at home too (the mock's count is
`(now // 60) % 4`), so there is no "mock must not be empty" fence to write
here — the emptiness itself is provider-independent.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.live_alarm import data
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    ALID_KIND,
    AlarmEvent,
    LiveAlarmPayload,
)


TOOL_TYPE = "cd-sem"
# A fab in the mock's _CONFIGURED_FABS, and a real fab at the office.
CONFIGURED_FAB = "R3"
# Deliberately not a fab anywhere: absent from the mock's whitelist AND from
# the office sem_list roster, so both must call it "not_configured".
UNKNOWN_FAB = "ZZZ-NOT-A-FAB"


def _is_mock() -> bool:
    return get_data_provider("live_alarm") == "mock"


def test_get_board_matches_contract():
    assert_matches(data.get_board(TOOL_TYPE, CONFIGURED_FAB), LiveAlarmPayload)


def test_events_match_contract():
    board = data.get_board(TOOL_TYPE, CONFIGURED_FAB)
    assert isinstance(board["events"], list)
    for event in board["events"]:
        assert_matches(event, AlarmEvent)


def test_every_event_carries_a_known_kind():
    # ALID_KIND is SKEWNONO's statement of which alarm ids the board can
    # render. If the office feed ever carries a third alid, the board would
    # render it with no kind — so this stays UNFENCED,
    # and reports the drift rather than dying with a bare KeyError.
    for event in data.get_board(TOOL_TYPE, CONFIGURED_FAB)["events"]:
        expected = ALID_KIND.get(event["alid"])
        assert expected is not None, (
            f"event {event['id']!r} carries alid {event['alid']!r}, which is not "
            f"in ALID_KIND ({sorted(ALID_KIND)}) — the office feed and this "
            f"build have drifted"
        )
        assert event["kind"] == expected


def test_events_are_newest_first():
    # Both providers sort by occurred_epoch desc; the board renders the list in
    # order, so an unsorted feed shows a stale alarm at the top.
    epochs = [event["occurred_epoch"] for event in data.get_board(TOOL_TYPE, CONFIGURED_FAB)["events"]]
    assert epochs == sorted(epochs, reverse=True)


def test_unknown_fab_is_not_configured_with_an_empty_board():
    # board.feed_status_for separates the three empty states for BOTH
    # providers: a fab absent from the mock whitelist / holding no tool of
    # this family in the roster is "미설정", never a healthy quiet board. A
    # typo'd fab must look the same at home as at the office.
    board = data.get_board(TOOL_TYPE, UNKNOWN_FAB)
    assert_matches(board, LiveAlarmPayload)
    assert board["feed_status"] == "not_configured"
    assert board["events"] == []
    assert board["fetched_at"] is None


def test_configured_fab_reports_a_heartbeat_state():
    if not _is_mock():
        # Mock-only: the whitelist is hardcoded in providers/mock.py, so R3 is
        # configured by construction. At the office the same fab is configured
        # only if the roster holds a tool of this family there, and
        # "not_configured" is then the correct answer rather than a failure. Skipped rather than
        # silently passed, so the office run reports that it did not check.
        pytest.skip(f"{CONFIGURED_FAB} is configured by construction only under mock")

    board = data.get_board(TOOL_TYPE, CONFIGURED_FAB)
    assert board["feed_status"] in {"live", "stale"}
    assert board["fetched_at"] is not None


def test_unmatched_count_is_always_present_and_non_negative():
    # A roster gap must be reportable on every board, including an empty one:
    # the field is what keeps "no alarms" distinguishable from "alarms we
    # could not attribute to any fab".
    for fab in (CONFIGURED_FAB, UNKNOWN_FAB):
        board = data.get_board(TOOL_TYPE, fab)
        assert isinstance(board["unmatched_count"], int)
        assert board["unmatched_count"] >= 0
