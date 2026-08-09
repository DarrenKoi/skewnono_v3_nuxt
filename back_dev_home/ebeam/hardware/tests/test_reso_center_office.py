"""Office Reso Center adapter tests.

These exercise the TRACKED template (`office_example`), never the gitignored
`office.py`, and never touch a cluster: every test feeds fabricated `_source`
dicts to the pure normalizer or monkeypatches `fetch_hits`.

Three properties this adapter exists to hold, and that a rewrite would most
plausibly break:

* the alias is `reso_center_cdsem`. `reso_center_log` is the value of each
  doc's `category` field and names no index — every .py and .md in this repo
  said otherwise until 2026-07-27, so it is pinned here rather than left to
  the next reader's judgement;
* the doc is exactly the mock's 13 flat fields. Focus Sweep was removed but
  its wide `Resolution_Range*` objects still ride along in `_source`
  (`enabled: false`), so they must not reach the page;
* `ResoDelta` is passed through as indexed, never recomputed from
  `ResoIScenter - BestReso`. Recomputing would silently repair the exact
  ingestion bug the two-line trend chart is meant to expose.
"""

from datetime import datetime, timedelta

import pytest

from back_dev_home.ebeam.hardware.providers.reso_center import (
    mock,
    office_example as office,
)


ANCHOR = datetime(2026, 5, 20, 9, 0)
START = ANCHOR - timedelta(days=14)
IP = "10.1.2.3"
EQP = "CDX001"

# A raw `_source` doc mirroring docs/datatables/hardware_reso_center_data.txt,
# with two source quirks the adapter has to absorb: numeric cells arriving as
# strings, and the dropped Focus Sweep objects still present in `_source`.
RAW_HIT = {
    "category": "reso_center_log",
    "CenterX": 1.15,
    "CenterY": "-0.99",
    "BestReso": 2.98,
    "ResoIScenter": "3.04",
    "ResoDelta": 0.06,
    "beam_condition": "HR0500_IP0080",
    "timestamp": "2026-05-20T12:55:16",
    "timestamp_date": "2026-05-20",
    "eqp_ip": IP,
    "eqp_id": EQP,
    "fac_id": "R3",
    "fab_name": "R3",
    # Focus Sweep leftovers — mapped enabled:false, still in _source.
    "Resolution_Range": {"0": 1.0},
    "Resolution_Range_Raw": {"0": 1.0},
    "fdc_category": "reso_center",
}


# ───────────────────────────── the alias itself ─────────────────────────────

def test_the_index_is_the_alias_not_the_category_value():
    """The defect this file is partly here to prevent recurring.

    `reso_center_log` is a `category` value. Until 2026-07-27 the template,
    hardware/MIGRATION.md and the design spec all named it as the index — a
    self-consistent codebase that was uniformly wrong, because every mention
    descended from one misreading. Only the datatables doc had it right.
    """
    assert office.INDEX == "reso_center_cdsem"
    assert office.CATEGORY == "reso_center_log"


# ─────────────────────────── pure coercion helper ───────────────────────────

def test_as_float_keeps_numeric_strings_and_rejects_bool_and_junk():
    assert office._as_float("3.04") == 3.04
    assert office._as_float(2.98) == 2.98
    # bool is an int subclass, so an unguarded coercion puts True on the chart
    # as 1.0 — a plausible-looking resolution.
    assert office._as_float(True) is None
    assert office._as_float("n/a") is None
    assert office._as_float(None) is None
    assert office._as_float(float("inf")) is None


# ──────────────────────────── doc normalization ─────────────────────────────

def test_normalized_doc_key_set_matches_the_mock_exactly():
    # The panel reads fields straight off each doc, so office and mock must
    # agree key-for-key. This is also what pins the Focus Sweep exclusion:
    # the mock has no Resolution_Range*, so a leak here fails the comparison.
    mock_doc = mock.build_reso_center_docs(EQP, "R3", START, ANCHOR)[0]
    assert set(office._normalize(RAW_HIT, EQP, IP)) == set(mock_doc)


def test_normalize_drops_the_focus_sweep_leftovers_riding_in_source():
    out = office._normalize(RAW_HIT, EQP, IP)
    for dropped in ("Resolution_Range", "Resolution_Range_Raw", "fdc_category"):
        assert dropped not in out


def test_normalize_coerces_numeric_strings_to_floats():
    out = office._normalize(RAW_HIT, EQP, IP)
    assert out["CenterY"] == -0.99
    assert out["ResoIScenter"] == 3.04
    assert all(isinstance(out[f], float) for f in office._NUMERIC_FIELDS)


def test_reso_delta_is_passed_through_as_indexed_not_recomputed():
    """A stored ResoDelta that disagrees with the difference is DATA, not a bug
    to fix here. Recomputing it would hide an ingestion fault behind a chart
    whose two lines then always match their own gap."""
    inconsistent = {**RAW_HIT, "BestReso": 2.98, "ResoIScenter": 3.04,
                    "ResoDelta": 0.99}
    out = office._normalize(inconsistent, EQP, IP)
    assert out["ResoDelta"] == 0.99  # not 0.06


def test_normalize_rejects_a_hit_belonging_to_another_tool():
    # A mismatch means the term clause matched more than intended (usually
    # .keyword mapping drift); rendering it would show another tool's data
    # under this tool's name.
    with pytest.raises(ValueError):
        office._normalize({**RAW_HIT, "eqp_ip": "10.9.9.9"}, EQP, IP)


def test_normalize_fills_an_absent_eqp_id_from_the_request():
    # The query selected this row BY IP, so it is this tool's even when the
    # index carries no eqp_id. A blank tool label on the panel would be worse
    # than the inference.
    out = office._normalize({**RAW_HIT, "eqp_id": ""}, EQP, IP)
    assert out["eqp_id"] == EQP


def test_normalize_rejects_an_empty_timestamp():
    with pytest.raises(ValueError):
        office._normalize({**RAW_HIT, "timestamp": ""}, EQP, IP)


# ───────────────────────── query shape + ordering ───────────────────────────

def _capture(monkeypatch, hits=()):
    """Record the fetch_hits call and serve canned hits."""
    calls = {}

    def fake_fetch_hits(index, query_body, size, sort=None, source=None):
        calls.update(index=index, body=query_body, size=size, sort=sort,
                     source=source)
        return list(hits)

    monkeypatch.setattr(office, "fetch_hits", fake_fetch_hits)
    monkeypatch.setattr(office, "_resolve_ip", lambda _eqp: IP)
    return calls


def test_build_filters_on_ip_window_and_fab(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_reso_center_docs(EQP, "R3", START, ANCHOR)

    assert calls["index"] == "reso_center_cdsem"
    clauses = calls["body"]["bool"]["filter"]
    assert {"term": {office.EQP_IP_KW: IP}} in clauses
    assert {"term": {office.FAB_NAME_KW: "R3"}} in clauses
    window = next(c for c in clauses if "range" in c)["range"][office.TIME_FIELD]
    assert window == {"gte": START.isoformat(), "lte": ANCHOR.isoformat()}
    # Only the 13 contract fields are requested, which is what keeps the
    # enabled:false Focus Sweep objects off the wire in the first place.
    assert calls["source"] == office.SOURCE_FIELDS


def test_build_omits_the_fab_term_when_not_given(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_reso_center_docs(EQP, None, START, ANCHOR)
    clauses = calls["body"]["bool"]["filter"]
    assert not any("fab_name" in str(c) for c in clauses)


def test_build_uppercases_the_fab_term(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_reso_center_docs(EQP, "m16a", START, ANCHOR)
    clauses = calls["body"]["bool"]["filter"]
    assert {"term": {office.FAB_NAME_KW: "M16A"}} in clauses


def test_build_sorts_by_timestamp_then_condition_like_the_mock(monkeypatch):
    # OpenSearch orders by timestamp alone, leaving same-second condition docs
    # in arbitrary order; both providers must hand the page one sequence.
    later = {**RAW_HIT, "timestamp": "2026-05-20T19:05:00"}
    same_second_a = {**RAW_HIT, "beam_condition": "HR0800_IP0080"}
    _capture(monkeypatch, hits=[later, same_second_a, RAW_HIT])

    out = office.build_reso_center_docs(EQP, "R3", START, ANCHOR)
    assert [(d["timestamp"], d["beam_condition"]) for d in out] == [
        ("2026-05-20T12:55:16", "HR0500_IP0080"),
        ("2026-05-20T12:55:16", "HR0800_IP0080"),
        ("2026-05-20T19:05:00", "HR0500_IP0080"),
    ]


def test_build_raises_when_the_result_fills_the_cap(monkeypatch):
    # A full cap means the window was probably truncated. Drawing a partial
    # history silently is the failure this refuses.
    _capture(monkeypatch, hits=[RAW_HIT] * office.MAX_DOCS)
    with pytest.raises(LookupError):
        office.build_reso_center_docs(EQP, "R3", START, ANCHOR)
