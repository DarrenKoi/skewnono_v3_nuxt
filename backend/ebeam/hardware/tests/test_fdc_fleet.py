"""FDC fab fleet view (`fdc-fleet`): one aggregation over the side-fields.

Pins the request body the office sends (`fleet.fleet_aggs`), the normalizer
both providers share (`fleet.fleet_from_aggs`) against a response shaped like
OpenSearch's, the office adapter's query, and the mock's emulation of that
response. No test here touches a cluster.
"""

import json
from datetime import datetime, timedelta
from statistics import fmean

import pytest

from backend._core.contract_check import assert_matches
from backend.ebeam.hardware.contracts import FdcFleet, HardwarePayload
from backend.ebeam.hardware.providers import mock as dispatcher
from backend.ebeam.hardware.providers.fdc import fleet, mock, office_example as office
from ops_index_mgmt.network_fdc_cdsem import side_fields


END = datetime(2026, 5, 24, 9, 0)
START = END - timedelta(days=30)


# ───────────────────────────── request body ─────────────────────────────────

def test_fleet_aggs_read_strings_on_keyword_and_numbers_bare():
    # Office 확인 2026-09-28: the index stays dynamically mapped, so strings
    # are text + .keyword (a terms agg on the bare field errors on fielddata)
    # while the numeric side-fields aggregate bare.
    body = json.dumps(fleet.fleet_aggs())
    for keyword in ("eqp_id.keyword", "pin_judgment.keyword", "pin_channel.keyword"):
        assert keyword in body
    for bare in ('"temp_c"', '"laser_x1"', '"laser_y1"', '"pin_spread"', '"pin_counter"'):
        assert bare in body
    # SPM is never fleet-compared: per-tool unit scales differ up to 100x.
    assert "spm_" not in body
    # The writer spells it `pin_judgment` (office 확인 2026-09-28). A wrong
    # name is not an error, just empty buckets forever, so pin it.
    assert "pin_judgment.keyword" in body and "judgement" not in body


def test_contactpin_counts_are_deduped_by_timestamp_cardinality():
    # The index holds byte-identical duplicates (0.38 % of Contactpin, 0.76 %
    # of Temperature on the busiest tools; office 확인 2026-09-28) and no two
    # DISTINCT docs of one tool share a timestamp, so cardinality(timestamp)
    # is exactly the deduped count, where doc_count would inflate the rates.
    # The threshold is explicit: busiest tools sit near the ~3000 default.
    judgment = fleet.fleet_aggs()["tools"]["aggs"]["judgment"]
    assert judgment["aggs"] == {"docs": {"cardinality": {
        "field": "timestamp", "precision_threshold": 40_000,
    }}}


# ───────────────────────────── normalizer ───────────────────────────────────

# Shaped like an OpenSearch answer: null avgs, key_as_string on date buckets,
# epoch-ms min/max on dates, float keys on histogram buckets.
RESPONSE = {
    "tools": {"buckets": [
        {
            "key": "ECX002", "doc_count": 40,
            "temp_c": {"value": None}, "laser_x1": {"value": None}, "laser_y1": {"value": None},
            "days": {"buckets": [{"key_as_string": "2026-05-01", "doc_count": 3, "temp_c": {"value": None}}]},
            "judgment": {"buckets": []},
            "channels": {"buckets": [{
                "key": "A", "doc_count": 1,
                "c_min": {"value": 100.0}, "c_max": {"value": 100.0},
                "t_min": {"value": 1.7e12}, "t_max": {"value": 1.7e12},
            }]},
        },
        {
            "key": "ECX001", "doc_count": 900,
            "temp_c": {"value": 23.4}, "laser_x1": {"value": 0.78}, "laser_y1": {"value": 0.73},
            "days": {"buckets": [
                {"key_as_string": "2026-05-01", "doc_count": 300, "temp_c": {"value": 23.39}},
                {"key_as_string": "2026-05-02", "doc_count": 1, "temp_c": {"value": None}},
            ]},
            "judgment": {"buckets": [
                {"key": "Conduction", "doc_count": 11, "docs": {"value": 10}},
                {"key": "NonConduction", "doc_count": 2, "docs": {"value": 2}},
            ]},
            "channels": {"buckets": [{
                "key": "B", "doc_count": 4,
                "c_min": {"value": 1000.0}, "c_max": {"value": 1060.0},
                "t_min": {"value": 0.0}, "t_max": {"value": 3 * 86_400_000.0},
            }]},
        },
    ]},
    "margin": {"buckets": [
        {"key": "Conduction", "spread": {"buckets": [
            {"key": 4.0, "doc_count": 7}, {"key": 6.0, "doc_count": 0},
        ]}},
    ]},
}


def test_fleet_from_aggs_normalizes_an_opensearch_shaped_response():
    out = fleet.fleet_from_aggs(RESPONSE, {"ECX001": "CG6300"})
    assert_matches(out, FdcFleet)
    first, second = out["tools"]
    assert [first["eqp_id"], second["eqp_id"]] == ["ECX001", "ECX002"]  # sorted
    assert first["eqp_model_cd"] == "CG6300" and second["eqp_model_cd"] is None
    assert first["temp_days"] == [{"day": "2026-05-01", "temp_c": 23.39}]  # null day dropped
    assert first["pin_counts"] == {"Conduction": 10, "NonConduction": 2}  # cardinality, not doc_count
    assert first["counter_rates"] == [{"channel": "B", "per_day": 20.0}]  # a rate, not the raw 1060
    # A tool with no docs of a key reads null/empty, never 0.
    assert second["temp_c"] is None and second["temp_days"] == [] and second["pin_counts"] == {}
    assert second["counter_rates"] == [{"channel": "A", "per_day": None}]  # zero span
    assert out["spread_bins"] == [
        {"judgment": "Conduction", "lo": 4.0, "count": 7},
        {"judgment": "Conduction", "lo": 6.0, "count": 0},
    ]
    assert out["spread_bin_width"] == fleet.SPREAD_BIN_WIDTH


# ───────────────────────────── office adapter ───────────────────────────────

ROSTER = [
    {"eqp_id": "ECX001", "eqp_model_cd": "CG6300", "fab_name": "M16A"},
    {"eqp_id": "ECX001", "eqp_model_cd": "GT2000", "fab_name": "M16A"},  # repeated id
    {"eqp_id": "ETP001", "eqp_model_cd": "TP3000", "fab_name": "M16A"},  # HV-SEM
    {"eqp_id": "ECX009", "eqp_model_cd": "CG6300", "fab_name": "R3"},   # other fab
]


def test_office_fleet_sends_one_aggregation_over_the_fab_cdsem_roster(monkeypatch):
    calls = []
    monkeypatch.setattr(office, "get_sem_list", lambda: ROSTER)
    monkeypatch.setattr(
        office, "aggregate",
        lambda index, aggs, query_body: calls.append((index, aggs, query_body)) or RESPONSE,
    )
    out = office.build_fdc_fleet("m16a", START, END)

    assert len(calls) == 1
    index, aggs, query_body = calls[0]
    assert index == office.INDEX and aggs == fleet.fleet_aggs()
    clauses = query_body["bool"]["filter"]
    # Roster ids, not a fab_name term: a stale fab label must not drop a tool.
    assert {"terms": {office.EQP_ID_KW: ["ECX001"]}} in clauses
    assert "fab_name" not in json.dumps(query_body)
    assert out["tools"][0]["eqp_model_cd"] == "CG6300"  # first roster row wins


def test_office_fleet_skips_the_request_for_a_fab_with_no_cdsem_roster(monkeypatch):
    monkeypatch.setattr(office, "get_sem_list", lambda: ROSTER)
    monkeypatch.setattr(office, "aggregate", lambda *a: pytest.fail("queried"))
    assert office.build_fdc_fleet("M99Z", START, END)["tools"] == []


# ───────────────────────────── mock emulation ───────────────────────────────

def test_mock_emulation_dedupes_counts_like_cardinality():
    doc = {"fdc_key": "ContactpinConductionInfo", "timestamp": "2026-05-01T00:00:00",
           "values": ["ContactpinConductionInfo", "0", "A", "3", "Conduction",
                      "-5.0", "-5.0", "0.0", "5.0", "100"]}
    doc = {**doc, **side_fields(doc)}
    aggs = mock._emulate_fleet_aggs({"ECX001": [doc, dict(doc)]})  # an exact duplicate
    out = fleet.fleet_from_aggs(aggs, {})
    assert out["tools"][0]["pin_counts"] == {"Conduction": 1}


def test_mock_fleet_means_match_the_raw_mock_docs():
    # The emulation must answer what OpenSearch would: cross-check one tool's
    # window mean against its raw docs, parsed independently of side_fields.
    out = mock.build_fdc_fleet("R3", START, END)
    assert_matches(out, FdcFleet)
    tool = next(t for t in out["tools"] if t["temp_c"] is not None)
    raw = mock.build_fdc_docs(tool["eqp_id"], "R3", START, END)
    temps = [float(d["values"][3]) for d in raw if d["fdc_key"] == "TemperatureEChuck"]
    assert tool["temp_c"] == pytest.approx(fmean(temps))
    assert len(tool["temp_days"]) >= 25  # a 30-day window, most days logged


def test_mock_fleet_covers_only_the_fabs_cdsem_roster_and_follows_model_coverage():
    roster = fleet.fab_roster(mock.get_sem_list(), "R3")
    out = mock.build_fdc_fleet("R3", START, END)
    assert {t["eqp_id"] for t in out["tools"]} <= set(roster)
    for tool in out["tools"]:
        if tool["eqp_model_cd"] in ("GT2000", "GT2000S"):
            assert tool["pin_counts"] == {} and tool["counter_rates"] == []
    assert {b["judgment"] for b in out["spread_bins"]} == {
        "Conduction", "UnstableConduction", "NonConduction",
    }


# ───────────────────────────── dispatcher ───────────────────────────────────

def test_fdc_fleet_payload_and_gates():
    payload = dispatcher.get_hardware_service("cdsem", "fdc-fleet", "CDX001", "R3", START, END)
    assert_matches(payload, HardwarePayload)
    assert payload["available"] and "fleet" in payload and "docs" not in payload
    no_fab = dispatcher.get_hardware_service("cdsem", "fdc-fleet", "CDX001", None, START, END)
    assert not no_fab["available"]
    hvsem = dispatcher.get_hardware_service("hvsem", "fdc-fleet", "TP0001", "R3", START, END)
    assert not hvsem["available"]
