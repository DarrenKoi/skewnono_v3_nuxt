"""Office FDC adapter tests.

These exercise the TRACKED template (`fdc/office_example`), never the
gitignored `fdc/office.py`, and never touch a cluster: every test feeds
fabricated `_source` dicts to the pure validator or monkeypatches
`fetch_hits`. A test here that takes measurable time has opened a socket and
is wrong — company data is unreachable from home by design.

Why this file exists: the only FDC office artifacts before it were
`scripts/diagnose_fdc_office.py` and `scripts/diagnose_fdc_standalone.py`,
and `openwiki/testing/guidance.md` says outright those are "not substitutes
for contract tests". The dispatcher already refuses to fall back to mock when
a wired adapter breaks (`test_contract.py`), so an FDC adapter that
mis-validates or mis-orders is guaranteed to reach the page — nothing
downstream second-guesses it.

The invariants pinned here are the ones that fail SILENTLY at the office: the
`.keyword` sub-field the term query depends on (the bare field errors on
fielddata), the fab non-filter (a stale fab label must never empty a chart),
the `"None"` string coercion, and the tie-break that makes office and mock
hand the chart the same doc sequence.
"""

from datetime import datetime, timedelta

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload
from back_dev_home.ebeam.hitachi.hardware.providers import office_example as dispatcher
from back_dev_home.ebeam.hitachi.hardware.providers.fdc import (
    mock,
    office_example as office,
)


ANCHOR = datetime(2026, 5, 20, 9, 0)

# A raw `_source` doc mirroring docs/datatables/hardware_network_fdc_cdsem.txt: exactly
# the seven ingested fields, `values[0]` repeating `fdc_key`.
RAW_HIT = {
    "eqp_id": "6MCDE305",
    "eqp_model_cd": "CG6300",
    "fab_name": "M16A",
    "eqp_ip": "177.1.2.3",
    "fdc_key": "TemperatureEChuck",
    "timestamp": "2026-05-19T04:00:00",
    "values": ["TemperatureEChuck", "0", "1", "23.41000"],
}


def _hit(**overrides) -> dict:
    return {**RAW_HIT, **overrides}


# ───────────────────────────── doc validation ───────────────────────────────

def test_validate_passes_a_well_formed_doc_through_unchanged():
    out = office._validate(RAW_HIT, "6MCDE305")
    assert out == RAW_HIT
    # Same object contents, but a copy: the adapter must not mutate the hit it
    # was handed, since fetch_hits' caller owns it.
    assert out is not RAW_HIT


def test_validate_coerces_a_stringified_none_timestamp_into_a_named_failure():
    # An ingestion that writes a missing timestamp as the literal string
    # "None" is the failure this adapter is most exposed to: `str(None)` is
    # truthy, so an unguarded adapter would sort on it and render "None" as
    # the latest-measurement card. `_text` maps it to "", which trips the
    # empty-timestamp check instead.
    with pytest.raises(ValueError, match="empty timestamp"):
        office._validate(_hit(timestamp="None"), "6MCDE305")
    with pytest.raises(ValueError, match="empty timestamp"):
        office._validate(_hit(timestamp=None), "6MCDE305")


def test_validate_strips_surrounding_whitespace_from_the_sorted_fields():
    # timestamp and fdc_key are the two fields the sort key and the dispatcher
    # read, so they are the two the adapter normalizes. A padded timestamp
    # would sort into its own bucket ahead of every unpadded one.
    out = office._validate(
        _hit(timestamp="  2026-05-19T04:00:00  ", fdc_key=" TemperatureEChuck "),
        "6MCDE305",
    )
    assert out["timestamp"] == "2026-05-19T04:00:00"
    assert out["fdc_key"] == "TemperatureEChuck"


def test_validate_rejects_a_hit_belonging_to_another_tool():
    # A term query that silently matched a second tool would blend two tools'
    # temperatures into one trend line, which reads as instrument drift.
    with pytest.raises(ValueError, match="6MCDE999"):
        office._validate(_hit(eqp_id="6MCDE999"), "6MCDE305")


def test_validate_rejects_an_fdc_key_the_frontend_parser_has_never_seen():
    # `values` has no self-describing layout — the parser branches on fdc_key
    # alone. A new key would be parsed as whichever branch falls through, so
    # an unknown one must fail loudly rather than draw a blank chart.
    with pytest.raises(ValueError, match="unknown fdc_key"):
        office._validate(
            _hit(fdc_key="ColumnVacuum", values=["ColumnVacuum", "0", "1"]),
            "6MCDE305",
        )


@pytest.mark.parametrize("values", [None, [], "TemperatureEChuck", {}])
def test_validate_rejects_a_values_field_that_is_not_a_non_empty_list(values):
    with pytest.raises(ValueError, match="expected a non-empty list"):
        office._validate(_hit(values=values), "6MCDE305")


def test_validate_rejects_a_doc_whose_values_head_disagrees_with_its_fdc_key():
    # The index stores the key twice; the frontend reads one and the sort key
    # reads the other. Disagreement means the doc was assembled wrong upstream.
    with pytest.raises(ValueError, match="must agree"):
        office._validate(
            _hit(values=["LaserPower", "0", "0.78", "0.71"]), "6MCDE305"
        )


def test_known_fdc_keys_are_exactly_the_four_documented_shapes():
    # Pinned against the mock, which fabricates the same four layouts: adding
    # a key to one side only would make the two providers disagree about which
    # docs are legal.
    docs = mock.build_fdc_docs("CDX001", "R3", ANCHOR - timedelta(days=14), ANCHOR)
    assert {doc["fdc_key"] for doc in docs} == office.KNOWN_FDC_KEYS


def test_requested_source_fields_match_the_mock_doc_key_set_exactly():
    # The dispatcher swaps mock.py and office.py by name and hands `docs`
    # straight to the SPA. A field present on one side only shows up as an
    # absent chart series, never as an error, so pin the sets against
    # each other rather than against a literal list.
    mock_doc = mock.build_fdc_docs("CDX001", "R3", ANCHOR - timedelta(days=2), ANCHOR)[0]
    assert set(office.SOURCE_FIELDS) == set(mock_doc)
    assert set(RAW_HIT) == set(mock_doc)  # and this file's fixture is faithful


# ─────────────────────── query construction + fetching ──────────────────────

def _capture(monkeypatch, hits=()):
    """Record the fetch_hits call and serve canned hits."""
    calls = []

    def fake_fetch_hits(index, query_body, size, sort=None, source=None):
        calls.append(
            {"index": index, "query": query_body, "size": size,
             "sort": sort, "source": source}
        )
        return [dict(hit) for hit in hits]

    monkeypatch.setattr(office, "fetch_hits", fake_fetch_hits)
    return calls


def test_build_terms_on_the_keyword_subfield_and_ranges_on_the_bare_date(monkeypatch):
    # Confirmed at the office 2026-07-23: network_fdc_cdsem has no explicit
    # mapping, so dynamic mapping makes eqp_id text+keyword — a term on the
    # bare field matches nothing and an agg on it errors on fielddata.
    # timestamp is a real date, so it ranges and sorts bare.
    calls = _capture(monkeypatch)
    office.build_fdc_docs("6MCDE305", "M16A", ANCHOR - timedelta(days=30), ANCHOR)

    call = calls[0]
    assert call["index"] == office.INDEX
    assert office.EQP_ID_KW == "eqp_id.keyword"
    clauses = call["query"]["bool"]["filter"]
    assert {"term": {office.EQP_ID_KW: "6MCDE305"}} in clauses
    rng = next(c["range"][office.TS_FIELD] for c in clauses if "range" in c)
    assert rng == {"gte": "2026-04-20T09:00:00", "lte": "2026-05-20T09:00:00"}
    assert call["sort"] == [{office.TS_FIELD: {"order": "asc"}}]
    assert call["size"] == office.MAX_FDC_DOCS
    assert call["source"] == office.SOURCE_FIELDS


def test_build_does_not_filter_on_fab_under_any_spelling(monkeypatch):
    # eqp_id is already the lookup identity and a tool belongs to one fab, so
    # a second fab clause can only ever subtract: a stale label on either side
    # empties the chart with no error. `fab_id` is a banned misnomer
    # project-wide and must not appear at all.
    calls = _capture(monkeypatch)
    office.build_fdc_docs("6MCDE305", "M16A", ANCHOR - timedelta(days=1), ANCHOR)

    rendered = repr(calls[0]["query"])
    for spelling in ("fab_name", "fab_id", "fac_id"):
        assert spelling not in rendered


def test_build_orders_docs_on_the_mocks_exact_tiebreak(monkeypatch):
    # OpenSearch sorts on timestamp alone, leaving the A/B/C and 1/2/3 docs
    # that share a second in arbitrary order. Both providers must re-sort on
    # (timestamp, fdc_key, values[2:3]) or the two phases hand the chart
    # different sequences for identical data.
    #
    # The expected sequence is written out literally rather than re-derived
    # from the adapter's own key — a test that re-applies the key it is
    # checking passes for ANY key, which is exactly how the sibling sharpness
    # adapter's numeric/lexicographic divergence went unnoticed.
    _capture(monkeypatch, hits=[
        _hit(fdc_key="TemperatureEChuck",
             values=["TemperatureEChuck", "0", "3", "23.55"]),
        _hit(fdc_key="LaserPower",
             values=["LaserPower", "0", "0.78", "0.71", "330000000", "44000000"]),
        _hit(fdc_key="TemperatureEChuck",
             values=["TemperatureEChuck", "0", "1", "23.41"]),
        _hit(timestamp="2026-05-18T04:00:00"),  # earlier, delivered last
    ])
    docs = office.build_fdc_docs("6MCDE305", None, ANCHOR - timedelta(days=5), ANCHOR)

    assert [(d["timestamp"], d["fdc_key"], d["values"][2]) for d in docs] == [
        ("2026-05-18T04:00:00", "TemperatureEChuck", "1"),  # earlier day first
        ("2026-05-19T04:00:00", "LaserPower", "0.78"),      # fdc_key breaks the
        ("2026-05-19T04:00:00", "TemperatureEChuck", "1"),  # timestamp tie…
        ("2026-05-19T04:00:00", "TemperatureEChuck", "3"),  # …then values[2]
    ]


def test_build_returns_an_empty_list_rather_than_raising_for_a_tool_with_no_docs(
    monkeypatch,
):
    # FDC is not in CDSEM_ONLY_SERVICES, so an HV-SEM tool reaches this adapter
    # and legitimately matches nothing. Empty is the intended answer until
    # HV-SEM FDC is ingested — not an error, and not a fallback to mock.
    _capture(monkeypatch)
    assert office.build_fdc_docs("TP0001", None, ANCHOR - timedelta(days=30), ANCHOR) == []


def test_build_raises_when_the_result_fills_the_cap(monkeypatch):
    # One non-paginated request. Filling the cap means the "a few thousand docs
    # per 30-day window" assumption broke, and a truncated history drawn as a
    # complete one is unfalsifiable from the chart.
    _capture(monkeypatch, hits=[RAW_HIT] * office.MAX_FDC_DOCS)
    with pytest.raises(LookupError, match="cap"):
        office.build_fdc_docs("6MCDE305", None, ANCHOR - timedelta(days=30), ANCHOR)


# ───────────────────── dispatcher → contract, office path ───────────────────

def test_office_fdc_payload_matches_the_hardware_contract(monkeypatch):
    """The whole office FDC path — adapter plus normalizer — against the contract.

    Wires the tracked FDC template in as if `fdc/office.py` had been copied,
    with `fetch_hits` faked, so the dispatcher branch that only ever runs at
    the office is exercised at home. Without this the adapter could satisfy
    every unit test above and still hand `docs_payload` something the SPA
    cannot read.
    """
    _capture(monkeypatch, hits=[RAW_HIT])
    real_import = dispatcher.import_module

    def fake_import(name):
        return office if name.endswith(".fdc.office") else real_import(name)

    monkeypatch.setattr(dispatcher, "import_module", fake_import)
    payload = dispatcher.get_hardware_service(
        "cdsem", "fdc", "6MCDE305", "M16A", ANCHOR - timedelta(days=14), ANCHOR
    )

    assert_matches(payload, HardwarePayload)
    # docs_payload's discriminated-by-service convention: fdc populates `docs`
    # and never `settings`. The frontend branches on which key is present.
    assert payload["docs"] == [RAW_HIT]
    assert "settings" not in payload
    assert payload["fab_name"] == "M16A"  # the label comes from the payload…
    latest = next(c for c in payload["cards"] if c["key"] == "latest_ts")
    assert latest["value"] == RAW_HIT["timestamp"]  # …not from the docs
