"""Pure board logic. No Redis, no Flask — every 'now' is injected."""

from back_dev_home.ebeam.hitachi.live_alarm import board
from back_dev_home.ebeam.hitachi.live_alarm.contracts import STALE_AFTER_SEC


def _meta(fetched_at: int) -> dict:
    return {"fetched_at": fetched_at}


def test_unknown_fab_is_not_configured():
    # The roster holds no tool of this type in this fab, which is a different
    # fact from "the feed died" and must look different on screen.
    assert board.feed_status_for(_meta(1000), known=False, now=1000) == "not_configured"


def test_feed_status_reads_fetched_at_not_polled_at():
    # polled_at was the writer's heartbeat; fetched_at is stamped only after a
    # SUCCESSFUL office call. A meta blob carrying the old key must read as
    # stale rather than being silently accepted as a fresh feed.
    assert board.feed_status_for({"polled_at": 1000}, known=True, now=1000) == "stale"
    assert board.feed_status_for(_meta(1000), known=True, now=1000) == "live"


def test_missing_meta_on_a_known_fab_is_stale():
    assert board.feed_status_for(None, known=True, now=1000) == "stale"


def test_fresh_meta_is_live():
    assert board.feed_status_for(_meta(1000), known=True, now=1000) == "live"


def test_exactly_at_threshold_is_still_live():
    now = 1000 + STALE_AFTER_SEC
    assert board.feed_status_for(_meta(1000), known=True, now=now) == "live"


def test_one_second_past_threshold_is_stale():
    now = 1000 + STALE_AFTER_SEC + 1
    assert board.feed_status_for(_meta(1000), known=True, now=now) == "stale"


def test_dedupe_keeps_one_row_per_id():
    rows = [
        {"id": "EQ1|9006|t", "alarm_name": "B"},
        {"id": "EQ1|9006|t", "alarm_name": "A"},
        {"id": "EQ2|9006|t", "alarm_name": "C"},
    ]
    out = board.dedupe_by_id(rows)
    assert len(out) == 2


def test_dedupe_is_deterministic_regardless_of_input_order():
    # Two reader processes must render the same screen from the same ZSET.
    a = {"id": "EQ1|9006|t", "alarm_name": "B"}
    b = {"id": "EQ1|9006|t", "alarm_name": "A"}
    assert board.dedupe_by_id([a, b]) == board.dedupe_by_id([b, a])


def test_parse_members_decodes_bytes():
    raw = [b'{"id":"EQ1|9006|t","occurred_epoch":1,"eqp_id":"EQ1"}']
    assert board.parse_members(raw) == [
        {"id": "EQ1|9006|t", "occurred_epoch": 1, "eqp_id": "EQ1"}
    ]


def test_parse_members_skips_a_broken_member():
    # Members outlive the build that wrote them, so a schema change or a
    # rolling restart must not take the whole endpoint down.
    raw = [
        b'{"id":"ok","occurred_epoch":1}',
        b'not json at all',
        b'{"id":"also-ok","occurred_epoch":2}',
    ]
    assert [e["id"] for e in board.parse_members(raw)] == ["ok", "also-ok"]


def test_parse_members_survives_every_member_being_broken():
    assert board.parse_members([b'{{{', b'}}}']) == []


def test_parse_members_drops_a_non_dict_member():
    # Valid JSON, wrong shape: a list would raise in dedupe_by_id's .get().
    raw = [b'[1,2,3]', b'{"id":"ok","occurred_epoch":1}']
    assert [e["id"] for e in board.parse_members(raw)] == ["ok"]


def test_parse_members_drops_a_dict_missing_required_keys():
    # Missing occurred_epoch would raise in the reader's sort key.
    raw = [
        b'{"id":"no-epoch"}',
        b'{"occurred_epoch":1}',
        b'{"id":"ok","occurred_epoch":1}',
    ]
    assert [e["id"] for e in board.parse_members(raw)] == ["ok"]
