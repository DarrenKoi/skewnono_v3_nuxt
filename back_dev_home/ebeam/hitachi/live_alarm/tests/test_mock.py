"""What the live_alarm MOCK must be able to represent.

Not a contract test — `test_contract.py` already guards the payload shape for
whichever provider is active. This file guards the mock's VALUE DOMAIN: the
range of situations a home session can actually see on screen.

That distinction earned its own file on 2026-08-03. The board grew a 측정 실패
view that groups by `(eqp_id, ppid)` and ranks by count, and the mock at the
time emitted 0..3 events spread across a dozen tools — so two alarms sharing a
tool AND a recipe essentially never occurred. Every path the grouping added was
unreachable at home, and a mock that cannot produce a repeat is quietly
asserting that repeats do not happen, which is the premise the screen was built
on. Shape tests all passed throughout; nothing was watching the value domain.

The clock is pinned per test rather than faked globally: the mock derives its
board from the current minute, so a test that reads the wall clock would assert
against a different board every 60 seconds.
"""

from __future__ import annotations

import collections

import pytest

from back_dev_home.ebeam.hitachi.live_alarm.providers import mock


TOOL_TYPE = "cd-sem"
# A fab the sem_list mock roster carries, so the board is `live` rather than
# `not_configured`.
FAB = "M16A"

# An arbitrary fixed epoch. Any value works — what matters is that a test names
# its minute instead of inheriting the wall clock.
BASE = 1_785_700_000
MINUTE = 60


@pytest.fixture
def at_minute(monkeypatch):
    """Pin the mock's clock to BASE + n minutes."""

    def _at(n: int):
        monkeypatch.setattr(mock.time, "time", lambda: BASE + n * MINUTE)
        return mock.get_board(TOOL_TYPE, (FAB,))

    return _at


def _meas_groups(board) -> collections.Counter:
    return collections.Counter(
        (event["eqp_id"], event["ppid"])
        for event in board["events"]
        if event["kind"] == "meas"
    )


def _cycle_boards(at_minute) -> list:
    """One board per minute across a full turn of the volume cycle.

    Sized from the cycle itself rather than hardcoded, so widening the cycle
    does not silently leave the tail of it untested.
    """
    return [at_minute(n) for n in range(len(mock._COUNTS))]


def test_some_minute_repeats_one_tool_and_recipe(at_minute):
    # THE regression this file exists for. The 측정 실패 view groups by
    # (eqp_id, ppid) and ranks by count; if no board can hold two meas alarms
    # sharing that pair, the grouped view renders as a flat list of singletons
    # at home and none of its behaviour is developable.
    best = max(
        (max(_meas_groups(board).values(), default=0) for board in _cycle_boards(at_minute)),
        default=0,
    )
    assert best >= 2, (
        "no minute in the volume cycle produces two measurement failures "
        "sharing an (eqp_id, ppid) — the grouped 측정 실패 view has nothing "
        "to group at home"
    )


def test_the_repeat_is_pronounced_enough_to_rank(at_minute):
    # A pile of 2 is a repeat; the screen's argument is "이 PPID 하나가 이만큼
    # 터졌다". A board whose largest group is 2 makes the count column look
    # like noise, so the busiest minute must produce a visibly dominant group.
    best = max(
        (max(_meas_groups(board).values(), default=0) for board in _cycle_boards(at_minute)),
        default=0,
    )
    assert best >= 4


def test_an_empty_board_stays_reachable(at_minute):
    # Raising the volume must not cost the empty state. "최근 20분간 알람이
    # 없습니다." is a real screen, and a mock that is never quiet means nobody
    # sees it until the office does.
    assert any(board["events"] == [] for board in _cycle_boards(at_minute))
    for board in _cycle_boards(at_minute):
        # Quiet is not the same as unconfigured: an empty board here is still
        # a live feed, which is the distinction board.feed_status_for exists
        # to make.
        assert board["feed_status"] in {"live", "stale"}


def test_the_same_minute_rebuilds_the_same_board(at_minute):
    # Determinism is what keeps the tests stable and lets a developer reload
    # the page without the board reshuffling under them.
    assert at_minute(1) == at_minute(1)


def test_ids_are_unique_within_a_board(at_minute):
    # `id` is the dedupe key for the ZSET and the frontend's new-arrival diff.
    # Two events sharing one id would make a genuinely new alarm read as
    # already-seen.
    for board in _cycle_boards(at_minute):
        ids = [event["id"] for event in board["events"]]
        assert len(ids) == len(set(ids))


def test_ids_do_not_collide_between_adjacent_minutes(at_minute):
    # The frontend decides "new since the last poll" by id (diffNewIds), and
    # consecutive polls routinely straddle a minute boundary. If minute N's
    # event 12 could carry the same id as minute N+1's event 2, a new alarm
    # would silently fail to highlight — a bug in the mock that would look
    # exactly like a bug in the highlight feature.
    seen: dict[str, int] = {}
    for n in range(len(mock._COUNTS)):
        for event in at_minute(n)["events"]:
            assert event["id"] not in seen or seen[event["id"]] == n, (
                f"id {event['id']!r} appears in minute {seen.get(event['id'])} "
                f"and again in minute {n}"
            )
            seen[event["id"]] = n


def test_the_roster_gap_path_stays_reachable(at_minute):
    # unmatched_count > 0 is the "the feed carried alarms we could not attribute
    # to any fab" screen. It used to be keyed on `count == 3`, so widening the
    # volume cycle past 3 would have made it unreachable at home without
    # failing a single test — the exact class of silent loss this file exists
    # to catch.
    assert any(board["unmatched_count"] > 0 for board in _cycle_boards(at_minute))


def test_a_blank_ppid_still_occurs(at_minute):
    # `_RECIPES` carries an empty string on purpose: the office sends "" rather
    # than omitting the key, and the board buckets those under "(PPID 없음)".
    # Losing that value would leave the bucket unreachable at home.
    assert any(
        ppid == "" for board in _cycle_boards(at_minute) for (_, ppid) in _meas_groups(board)
    )


def test_mock_board_stamps_event_fab():
    payload = mock.get_board("cd-sem", ("R3", "M16B"))
    assert payload["fab_names"] == ["R3", "M16B"]
    for event in payload["events"]:
        assert event["fab_name"] in {"R3", "M16B"}


def test_mock_board_partial_not_configured():
    payload = mock.get_board("cd-sem", ("R3", "NOPE"))
    assert payload["not_configured_fabs"] == ["NOPE"]
    assert payload["feed_status"] != "not_configured"


def test_mock_board_all_unconfigured_is_not_configured():
    payload = mock.get_board("cd-sem", ("NOPE1", "NOPE2"))
    assert payload["feed_status"] == "not_configured"
    assert payload["not_configured_fabs"] == ["NOPE1", "NOPE2"]
