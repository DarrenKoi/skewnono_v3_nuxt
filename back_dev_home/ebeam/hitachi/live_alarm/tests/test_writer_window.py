"""Adaptive backfill. A fixed window loses alarms whenever the writer
stalls longer than that window, and the heartbeat still reads fresh —
so the loss is invisible. These tests pin the recovery behaviour."""

from back_dev_home.ebeam.hitachi.live_alarm.writer import window
from back_dev_home.ebeam.hitachi.live_alarm.writer.window import (
    BOARD_WINDOW_SEC,
    POLL_WINDOW_SEC,
    compute_window,
)


NOW = 1_000_000


def test_steady_state_uses_the_normal_window():
    window, _ = compute_window(NOW - 15, events_key_exists=True, now=NOW)
    assert window == POLL_WINDOW_SEC


def test_a_short_gap_still_uses_the_normal_window():
    # 45s gap is inside the 60s window already — no widening needed.
    window, _ = compute_window(NOW - 45, events_key_exists=True, now=NOW)
    assert window == POLL_WINDOW_SEC


def test_a_gap_past_the_window_widens_the_query():
    # This is the case a fixed 60s window loses silently.
    window, _ = compute_window(NOW - 75, events_key_exists=True, now=NOW)
    assert window > POLL_WINDOW_SEC
    assert window >= 75


def test_a_huge_gap_is_capped_at_the_board_horizon():
    # The board only ever shows 10 minutes, so a 10-minute query fully
    # rebuilds it however long the outage was. No partial-recovery state.
    window, _ = compute_window(NOW - 86_400, events_key_exists=True, now=NOW)
    assert window == BOARD_WINDOW_SEC


def test_no_previous_poll_is_a_cold_start():
    window, _ = compute_window(None, events_key_exists=True, now=NOW)
    assert window == BOARD_WINDOW_SEC


def test_a_missing_events_key_forces_a_cold_start():
    # Redis restart or maxmemory eviction. Without this the next poll would
    # write 60 seconds of events plus a fresh heartbeat, producing an empty
    # board that claims to be live.
    window, _ = compute_window(NOW - 15, events_key_exists=False, now=NOW)
    assert window == BOARD_WINDOW_SEC


def test_covered_since_matches_the_window():
    window, covered_since = compute_window(NOW - 75, events_key_exists=True, now=NOW)
    assert covered_since == NOW - window


def test_poll_window_is_configurable(monkeypatch):
    # POLL_WINDOW_SEC is read from LIVE_ALARM_POLL_WINDOW_SEC at import; the
    # steady-state floor must reflect whatever value that produced, not a
    # hardcoded 60. Patching the module constant proves it flows into the math.
    monkeypatch.setattr(window, "POLL_WINDOW_SEC", 30)
    steady, _ = compute_window(NOW - 5, events_key_exists=True, now=NOW)
    assert steady == 30
