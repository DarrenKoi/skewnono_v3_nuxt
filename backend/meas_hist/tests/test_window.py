"""Measurements around one hardware timestamp (`/api/meas-hist/window`).

The hardware tabs link a clicked time to the recipes measured on that tool
within +-30 minutes. A measurement counts when its start-end span overlaps the
window. Times are offset-less KST wall clock on both sides.
"""

from datetime import datetime, timedelta

import pytest

from backend import create_app
from backend._core.contract_check import assert_matches
from backend.ebeam._tool_specs import model_to_tool_type
from backend.meas_hist.contracts import MeasHistWindowResponse
from backend.meas_hist.providers import mock, office_example
from backend.sem_list.providers.mock import get_sem_list


AT = datetime(2026, 9, 29, 10, 0)
HALF = timedelta(minutes=30)


def _cdsem_tool() -> str:
    return next(r["eqp_id"] for r in get_sem_list() if model_to_tool_type(r["eqp_model_cd"]) == "cd-sem")


def _wall(value: str) -> datetime:
    # Mock rows carry the KST wall clock with a Z tag (the office convention).
    return datetime.fromisoformat(value.replace("Z", ""))


# ───────────────────────────── mock ─────────────────────────────────────────

def test_mock_window_rows_belong_to_the_tool_and_overlap_the_window():
    eqp_id = _cdsem_tool()
    hits = [
        mock.find_meas_hist_in_window(eqp_id, AT + timedelta(hours=h) - HALF, AT + timedelta(hours=h) + HALF)
        for h in range(24)
    ]
    rows = [row for day in hits for row in day]
    assert rows, "a working CD-SEM must measure something within a day"
    for h, day in enumerate(hits):
        start, end = AT + timedelta(hours=h) - HALF, AT + timedelta(hours=h) + HALF
        for row in day:
            assert row["eqp_id"] == eqp_id
            assert _wall(row["start_time"]) < end and _wall(row["end_time"]) > start


def test_mock_window_is_stable_across_overlapping_windows():
    # The same measurement must look the same from any window that sees it.
    eqp_id = _cdsem_tool()
    wide = mock.find_meas_hist_in_window(eqp_id, AT - timedelta(hours=3), AT + timedelta(hours=3))
    narrow = mock.find_meas_hist_in_window(eqp_id, AT - HALF, AT + HALF)
    assert all(row in wide for row in narrow)
    assert mock.find_meas_hist_in_window(eqp_id, AT - HALF, AT + HALF) == narrow


def test_mock_window_is_empty_for_a_tool_outside_the_roster():
    assert mock.find_meas_hist_in_window("NOPE999", AT - HALF, AT + HALF) == []


# ───────────────────────────── office ───────────────────────────────────────

def test_office_window_query_matches_overlap_or_timestamp_for_one_tool(monkeypatch):
    captured = {}

    class _Fake:
        def search_raw(self, body):
            captured["body"] = body
            return {"hits": {"total": {"value": 0}, "hits": []}}

    monkeypatch.setattr(office_example, "_os_search", lambda _index: _Fake())
    assert office_example.find_meas_hist_in_window("ecdx101", AT - HALF, AT + HALF) == []
    query = captured["body"]["query"]["bool"]
    assert {"term": {"eqp_id.keyword": "ECDX101"}} in query["filter"]
    assert query["minimum_should_match"] == 1
    text = str(query["should"])
    # Offset-less bounds: the index stores KST wall clock without an offset.
    assert "2026-09-29T09:30:00" in text and "2026-09-29T10:30:00" in text
    assert "start_time" in text and "end_time" in text and "timestamp" in text
    assert "+" not in text and "Z" not in text


# ───────────────────────────── route ────────────────────────────────────────

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.set_cookie("LASTUSER", "local-dev")
        yield c


def test_window_route_returns_the_contract_for_plus_minus_30_minutes(client):
    eqp_id = _cdsem_tool()
    response = client.get(f"/api/meas-hist/window?eqp_id={eqp_id}&at=2026-09-29T10:00:00")
    assert response.status_code == 200
    body = response.get_json()
    assert_matches(body, MeasHistWindowResponse)
    assert (body["start"], body["end"]) == ("2026-09-29T09:30:00", "2026-09-29T10:30:00")


def test_window_route_reads_an_offset_as_an_instant_and_converts_to_kst(client):
    response = client.get(f"/api/meas-hist/window?eqp_id={_cdsem_tool()}&at=2026-09-29T01:00:00Z")
    assert response.get_json()["at"] == "2026-09-29T10:00:00"


@pytest.mark.parametrize("query", ["at=2026-09-29T10:00:00", "eqp_id=ECDX101", "eqp_id=ECDX101&at=nope"])
def test_window_route_rejects_a_missing_or_bad_argument(client, query):
    assert client.get(f"/api/meas-hist/window?{query}").status_code == 400
