"""Office BSM adapter tests.

These exercise the TRACKED template (`office_example`), never the gitignored
`office.py`, and never touch a cluster: every test feeds fabricated `_source`
dicts to the pure normalizers or monkeypatches `fetch_hits`.

The two real-source shapes the adapter exists to fix are pinned here: the
doubly-nested `Reso EB Focus` (`[[...16...]]`) and the one-element
`Reso EB Focus Range` (`['8.0000']`), plus the mixed float/numeric-string
cells the source stores within a single per-degree array.
"""

from datetime import datetime, timedelta

import pytest

from back_dev_home.ebeam.hardware.providers.bsm import (
    mock,
    office_example as office,
)


ANCHOR = datetime(2026, 5, 20, 9, 0)
DEGREES = [round(i * 22.5, 1) for i in range(16)]


def _arr16(base: float) -> list[float]:
    return [round(base + i * 0.01, 5) for i in range(16)]


# A raw `_source` doc mirroring docs/datatables/hardware_beam_shape.txt: Reso EB Focus is
# doubly-nested and string-valued, Range is a one-element list, Noise mixes a
# float and a numeric string.
RAW_HIT = {
    "category": "I-diff_hp",
    "degree": list(DEGREES),
    "Reso EB Focus Range": ["8.0000"],
    "Reso EB Focus": [[f"{8.9 + i * 0.01:.5f}" for i in range(16)]],
    "Reso EB": _arr16(8.06),
    "Reso Detector": _arr16(0.0056),
    "Noise": [6.069593, "6.118456"] + _arr16(6.1)[2:],
    "Focus offset": _arr16(4.67),
    "Apature angle factor": _arr16(0.00117),
    "Major Axis": 8.124588,
    "Minor Axis": 7.941668,
    "Ellipicity": 1.023033,
    "Tilt": -35.09035,
    "X range": 8.06693,
    "Y range": 7.995835,
    "Area": 202.704313,
    "Ave. Reso Detector": 0.003042,
    "Ave. Noise": 6.27704,
    "Ave. Apature angle factor": 0.001214,
    "type": "total",
    "beam_condition": "HR0800_IP0080",
    "timestamp": "2026-05-20T14:15:00",
    "timestamp_date": "2026-05-20",
    "eqp_ip": "10.1.2.3",
    "eqp_id": "CDX001",
    "fac_id": "R3",
    "fab_name": "R3",
    "fdc_category": "bsi_beam_shape",
}


# ─────────────────────────── pure coercion helpers ──────────────────────────

def test_flatten16_unwraps_the_doubly_nested_reso_eb_focus():
    out = office._flatten16(RAW_HIT["Reso EB Focus"])
    assert out is not None
    assert len(out) == 16
    assert all(isinstance(x, float) for x in out)
    assert out[0] == pytest.approx(8.9)


def test_flatten16_coerces_a_mixed_float_and_string_array():
    out = office._flatten16([1.0, "2.5"] + _arr16(3.0)[2:])
    assert out is not None and len(out) == 16
    assert out[1] == pytest.approx(2.5)


def test_flatten16_rejects_a_non_16_array():
    assert office._flatten16([1, 2, 3]) is None
    assert office._flatten16("nope") is None
    assert office._flatten16([[1, 2, 3]]) is None  # unwrapped-but-short


def test_as_float_rejects_bool_and_junk_but_keeps_numeric_strings():
    assert office._as_float(True) is None
    assert office._as_float("abc") is None
    assert office._as_float(float("inf")) is None
    assert office._as_float("8.0000") == pytest.approx(8.0)


# ───────────────────────────── doc normalization ────────────────────────────

def test_normalize_flattens_focus_unwraps_range_and_coerces_cells():
    out = office._normalize(RAW_HIT)
    # Reso EB Focus is a flat length-16 float array (radar-ready).
    assert len(out["Reso EB Focus"]) == 16
    assert all(isinstance(x, float) for x in out["Reso EB Focus"])
    # Range is a scalar float (trend/KPI-ready), not a list.
    assert out["Reso EB Focus Range"] == pytest.approx(8.0)
    assert not isinstance(out["Reso EB Focus Range"], list)
    # Mixed float/string Noise cells all coerce to floats.
    assert all(isinstance(x, float) for x in out["Noise"])
    assert out["Noise"][1] == pytest.approx(6.118456)
    # Metadata passes through.
    assert out["beam_condition"] == "HR0800_IP0080"
    assert out["category"] == "I-diff_hp"
    assert out["type"] == "total"


def test_normalize_drops_a_malformed_profile_rather_than_emitting_it():
    hit = {**RAW_HIT, "Reso EB": _arr16(8.0)[:15]}  # only 15 cells
    out = office._normalize(hit)
    assert "Reso EB" not in out           # dropped: "if not 16 numbers we ignore"
    assert "Reso Detector" in out         # the well-formed ones survive


def test_normalized_doc_key_set_matches_the_mock_exactly():
    # The dispatcher swaps mock.py and office.py by name; divergent keys show up
    # as missing metrics rather than an error, so pin them against each other.
    mock_doc = mock.build_beam_shape_docs("CDX001", "R3", ANCHOR - timedelta(days=1), ANCHOR)[0]
    assert set(office._normalize(RAW_HIT)) == set(mock_doc)


# ─────────────────────── query construction + fetching ──────────────────────

def _capture(monkeypatch, hits=()):
    """Record the fetch_hits call and serve canned hits."""
    calls = []

    def fake_fetch_hits(index, query_body, size, sort=None, source=None):
        calls.append({"index": index, "query": query_body, "size": size, "sort": sort})
        return list(hits)

    monkeypatch.setattr(office, "fetch_hits", fake_fetch_hits)
    return calls


def test_build_filters_on_type_category_window_eqp_and_fab(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_beam_shape_docs("CDX001", "r3", ANCHOR - timedelta(days=30), ANCHOR)

    call = calls[0]
    assert call["index"] == office.INDEX
    clauses = call["query"]["bool"]["filter"]
    assert {"term": {office.TYPE_KW: "total"}} in clauses
    assert {"term": {office.FDC_CATEGORY_KW: "bsi_beam_shape"}} in clauses
    assert {"term": {office.EQP_ID_KW: "CDX001"}} in clauses
    assert {"term": {office.FAB_NAME_KW: "R3"}} in clauses  # uppercased
    rng = next(c["range"][office.TIME_FIELD] for c in clauses if "range" in c)
    assert rng["gte"] == "2026-04-20T09:00:00"
    assert rng["lte"] == "2026-05-20T09:00:00"
    assert call["sort"] == [{office.TIME_FIELD: "asc"}]


def test_build_omits_eqp_and_fab_terms_when_not_given(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_beam_shape_docs("", None, ANCHOR - timedelta(days=1), ANCHOR)
    rendered = repr(calls[0]["query"])
    assert office.EQP_ID_KW not in rendered
    assert office.FAB_NAME_KW not in rendered


def test_build_returns_normalized_docs_sorted_by_timestamp_then_condition(monkeypatch):
    later = {**RAW_HIT, "timestamp": "2026-05-20T22:00:00", "beam_condition": "HR0500_IP0080"}
    earlier_b = {**RAW_HIT, "beam_condition": "HR0900_IP0080"}
    _capture(monkeypatch, hits=[later, RAW_HIT, earlier_b])  # deliberately unordered
    docs = office.build_beam_shape_docs("CDX001", "R3", ANCHOR - timedelta(days=1), ANCHOR)

    order = [(d["timestamp"], d["beam_condition"]) for d in docs]
    assert order == sorted(order)
    assert len(docs[0]["Reso EB Focus"]) == 16  # normalized, not raw


def test_build_raises_when_the_result_fills_the_cap(monkeypatch):
    _capture(monkeypatch, hits=[RAW_HIT] * office.MAX_DOCS)
    with pytest.raises(LookupError, match="cap"):
        office.build_beam_shape_docs("CDX001", "R3", ANCHOR - timedelta(days=1), ANCHOR)
