"""Office sharpness adapter tests.

These exercise the TRACKED template (`sharpness/office_example`), never the
gitignored `sharpness/office.py`, and never touch a cluster or a roster: every
test feeds fabricated `_source` dicts to the pure validator, or monkeypatches
`fetch_hits` and `get_sem_list`. A test here that takes measurable time has
opened a socket and is wrong.

Sharpness is the one hardware adapter with TWO failure surfaces rather than
one, and both fail as an empty chart rather than an error:

* **Identity.** `sharpness_monitor_cdsem` carries no `eqp_id` at all, only
  `ip`, so every query goes eqp_id -> eqp_ip -> `ip` through the sem_list
  roster. A roster on the mock provider hands back fabricated IPs that match
  zero documents — indistinguishable from "this tool logged nothing".
* **Shape.** The page reads three 16-key per-degree objects straight off each
  doc. A missing or empty object renders as a blank radar, which is far harder
  to trace back to ingestion than a 500 naming the field.

Both are pinned below, along with the `"None"`-string coercion in the roster
join and the zero-valued condition key that a falsiness check would wrongly
reject.
"""

from datetime import datetime, timedelta

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload
from back_dev_home.ebeam.hitachi.hardware.providers import office_example as dispatcher
from back_dev_home.ebeam.hitachi.hardware.providers.sharpness import (
    mock,
    office_example as office,
)


ANCHOR = datetime(2026, 5, 20, 9, 0)

DEGREE_KEYS = [f"{round(i * 22.5, 1)}" for i in range(16)]
IP = "177.1.2.3"


def _profile(center: float) -> dict[str, float]:
    return {deg: round(center + i * 0.001, 6) for i, deg in enumerate(DEGREE_KEYS)}


# A raw `_source` doc mirroring docs/datatables/hardware_sharpness_monitor_cdsem.txt:
# exactly the eight ingested fields, nesting kept verbatim (NOT flattened).
RAW_HIT = {
    "ip": IP,
    "timestamp": "2026-05-19T09:17:00",
    "os_inserted": "2026-05-19T09:17:42",
    "beam_condition": {
        "Serial_No": "SN01234",
        "SEM_Cond_No": 6,
        "Vacc": 800,
        "Vsup": 1.8012,
        "Ip": 8.02,
        "Optics": "Optics_A",
        "Detector": "Upper",
        "AL3_x_offset": 0.0121,
        "AL3_y_offset": -0.0074,
    },
    "reso_detector": _profile(0.005),
    "noise": _profile(6.10),
    "reso_eb": _profile(8.00),
    "summ_beam": {
        "Ellipticity": 0.9412,
        "Major Axis": 3.4021,
        "Minor Axis": 3.2021,
        "Offset": 0.1122,
        "Tilt": -4.4021,
        "x_range": 3.0102,
        "y_range": 2.9881,
    },
}


def _hit(**overrides) -> dict:
    return {**RAW_HIT, **overrides}


def _sem_row(**overrides) -> dict:
    row = {"eqp_id": "MCD018", "eqp_ip": IP, "fab_name": "M16A", "fac_id": "M16"}
    row.update(overrides)
    return row


@pytest.fixture(autouse=True)
def _isolated_roster_cache():
    """Clear the module-level `ttl_cache` around every test.

    `_ip_by_eqp_id` memoizes for 15 minutes by design, so without this a
    roster faked by one test would silently answer the next one — and the
    failure would depend on test order.
    """
    office._ip_by_eqp_id.cache_clear()
    yield
    office._ip_by_eqp_id.cache_clear()


@pytest.fixture
def office_roster(monkeypatch):
    """Put sem_list on the office provider and serve a canned roster."""

    def _install(rows):
        monkeypatch.setattr(office, "get_data_provider", lambda feature: "office")
        monkeypatch.setattr(office, "get_sem_list", lambda: list(rows))

    return _install


# ─────────────────────────── identity resolution ────────────────────────────

def test_roster_on_the_mock_provider_is_refused_by_name(monkeypatch):
    # The whole point of the guard: mock sem_list hands back fabricated IPs
    # (177./197. nets rolled from an md5 seed), which term-match zero real
    # documents. Without this the page shows an empty radar and there is
    # nothing anywhere — log, response, chart — saying why.
    monkeypatch.setattr(office, "get_data_provider", lambda feature: "mock")
    monkeypatch.setattr(
        office, "get_sem_list", lambda: pytest.fail("roster must not be read")
    )
    with pytest.raises(LookupError, match="SKEWNONO_SEM_LIST_PROVIDER"):
        office._resolve_ip("MCD018")


def test_roster_drops_rows_whose_ip_stringifies_to_none(office_roster):
    # A tool with no IP recorded arrives as None, NaN, or the literal string
    # "None" depending on how the roster row was built. `_text` maps all three
    # to "", and the walrus guard drops the row — an entry mapping MCD777 to
    # the string "None" would term-query for "None" and return zero hits.
    office_roster([
        _sem_row(),
        _sem_row(eqp_id="MCD777", eqp_ip="None"),
        _sem_row(eqp_id="MCD888", eqp_ip=None),
        _sem_row(eqp_id="None", eqp_ip="177.9.9.9"),
    ])
    assert office._ip_by_eqp_id() == {"MCD018": IP}


def test_unknown_tool_names_itself_and_points_at_the_inventory_view(office_roster):
    office_roster([_sem_row()])
    with pytest.raises(LookupError, match="MCD999"):
        office._resolve_ip("MCD999")


# ───────────────────────────── doc validation ───────────────────────────────

def test_validate_passes_a_well_formed_doc_through_as_a_copy():
    out = office._validate(RAW_HIT, "MCD018", IP)
    assert out == RAW_HIT
    assert out is not RAW_HIT  # the caller owns the hit; do not mutate it


def test_validate_rejects_a_hit_carrying_another_tools_ip():
    with pytest.raises(ValueError, match="197.9.9.9"):
        office._validate(_hit(ip="197.9.9.9"), "MCD018", IP)


@pytest.mark.parametrize("timestamp", ["None", "", None, "  "])
def test_validate_coerces_a_stringified_none_timestamp_into_a_named_failure(timestamp):
    # As in FDC: `str(None)` is truthy, so an unguarded adapter would sort on
    # "None" and render it as the latest-measurement card.
    with pytest.raises(ValueError, match="empty timestamp"):
        office._validate(_hit(timestamp=timestamp), "MCD018", IP)


def test_validate_accepts_a_condition_key_whose_value_is_zero(office_roster):
    # `condition.get(key) is None`, deliberately, NOT falsiness: SEM_Cond_No 0
    # and Vacc 0 are legal stored values, and a `not condition.get(...)` check
    # would 500 the whole tab on a doc that is perfectly well formed.
    condition = {**RAW_HIT["beam_condition"], "SEM_Cond_No": 0, "Vacc": 0}
    out = office._validate(_hit(beam_condition=condition), "MCD018", IP)
    assert out["beam_condition"]["SEM_Cond_No"] == 0


@pytest.mark.parametrize("key", ["SEM_Cond_No", "Vacc"])
def test_validate_rejects_a_doc_missing_either_half_of_the_condition_pair(key):
    # The page's condition selector is built from the (SEM_Cond_No, Vacc) pair
    # — half a pair collapses two distinct beam conditions into one series.
    condition = {k: v for k, v in RAW_HIT["beam_condition"].items() if k != key}
    with pytest.raises(ValueError, match=key):
        office._validate(_hit(beam_condition=condition), "MCD018", IP)


@pytest.mark.parametrize("beam_condition", [None, "HR0800_IP0080", []])
def test_validate_rejects_a_beam_condition_that_is_not_an_object(beam_condition):
    # BSM stores its condition as a flat string; this index stores an object.
    # Copying the BSM shape here would pass a str to `.get` downstream.
    with pytest.raises(ValueError, match="expected an object"):
        office._validate(_hit(beam_condition=beam_condition), "MCD018", IP)


@pytest.mark.parametrize("field", ["reso_eb", "noise", "reso_detector", "summ_beam"])
@pytest.mark.parametrize("value", [None, {}, [], "0.005"])
def test_validate_rejects_an_empty_or_non_object_profile(field, value):
    # An empty per-degree object renders as a blank radar with no error
    # anywhere — the exact failure this validator exists to convert into a 500
    # that names the field.
    with pytest.raises(ValueError, match=field):
        office._validate(_hit(**{field: value}), "MCD018", IP)


def test_all_three_profiles_are_validated_not_just_the_default_one():
    # The page offers reso_eb / noise / reso_detector as interchangeable radar
    # metrics — which one is the real lever on tool condition is still open.
    # Validating only the default would let the other two arrive empty.
    assert set(office.PROFILE_FIELDS) == {"reso_eb", "noise", "reso_detector"}


def test_requested_source_fields_match_the_mock_doc_key_set_exactly():
    # The dispatcher swaps mock.py and office.py by name and hands `docs`
    # straight to the SPA; a field on one side only is an absent chart series,
    # never an error. Note there is no `eqp_id` on either side — that absence
    # is the whole reason this adapter resolves an IP first.
    mock_doc = mock.build_network_sharpness_docs(
        "MCD018", "M16A", ANCHOR - timedelta(days=2), ANCHOR
    )[0]
    assert set(office.SOURCE_FIELDS) == set(mock_doc)
    assert set(RAW_HIT) == set(mock_doc)  # and this file's fixture is faithful
    assert "eqp_id" not in mock_doc


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


def test_build_terms_on_the_bare_ip_field_not_a_keyword_subfield(
    monkeypatch, office_roster
):
    # Unlike network_fdc_cdsem, this index is externally managed with an
    # explicit mapping and `ip` is a real `keyword`. Copying FDC's
    # `.keyword` suffix here would match nothing.
    office_roster([_sem_row()])
    calls = _capture(monkeypatch)
    office.build_network_sharpness_docs(
        "MCD018", "M16A", ANCHOR - timedelta(days=30), ANCHOR
    )

    call = calls[0]
    assert call["index"] == office.INDEX
    assert office.IP_FIELD == "ip"
    clauses = call["query"]["bool"]["filter"]
    assert {"term": {"ip": IP}} in clauses
    rng = next(c["range"]["timestamp"] for c in clauses if "range" in c)
    assert rng == {"gte": "2026-04-20T09:00:00", "lte": "2026-05-20T09:00:00"}
    assert call["sort"] == [{"timestamp": {"order": "asc"}}]
    assert call["size"] == office.MAX_SHARPNESS_DOCS
    assert call["source"] == office.SOURCE_FIELDS


def test_build_never_filters_on_fab_because_the_index_has_no_fab_field(
    monkeypatch, office_roster
):
    # `fab_name` is accepted for dispatcher signature parity only. `fab_id` is
    # a banned misnomer project-wide and must not appear under any spelling.
    office_roster([_sem_row()])
    calls = _capture(monkeypatch)
    office.build_network_sharpness_docs(
        "MCD018", "M16A", ANCHOR - timedelta(days=1), ANCHOR
    )

    rendered = repr(calls[0]["query"])
    for spelling in ("fab_name", "fab_id", "fac_id"):
        assert spelling not in rendered


def test_build_breaks_timestamp_ties_on_the_condition_number(
    monkeypatch, office_roster
):
    # OpenSearch sorts on timestamp alone, so the two condition-pair docs
    # sharing a second arrive in arbitrary order. Both providers must re-sort
    # or the two phases hand the page different sequences for identical data.
    office_roster([_sem_row()])
    cond5 = {**RAW_HIT["beam_condition"], "SEM_Cond_No": 5, "Vacc": 500}
    _capture(monkeypatch, hits=[
        _hit(beam_condition=cond5, timestamp="2026-05-19T16:41:00"),
        _hit(timestamp="2026-05-19T16:41:00"),          # cond 6, same second
        _hit(beam_condition=cond5),                     # 09:17, delivered last
    ])
    docs = office.build_network_sharpness_docs(
        "MCD018", None, ANCHOR - timedelta(days=5), ANCHOR
    )

    assert [
        (d["timestamp"], d["beam_condition"]["SEM_Cond_No"]) for d in docs
    ] == [
        ("2026-05-19T09:17:00", 5),
        ("2026-05-19T16:41:00", 5),
        ("2026-05-19T16:41:00", 6),
    ]


def test_condition_tiebreak_is_numeric_and_agrees_with_the_mock(
    monkeypatch, office_roster
):
    """The tie-break must order conditions numerically, as the mock does.

    This was a real defect: the adapter coerced with
    `str(d["beam_condition"]["SEM_Cond_No"])` while `sharpness/mock.py` sorted
    the same field numerically. Since `"10" < "5"`, a two-digit condition number
    made the two providers hand the page different doc orders for identical
    data — defeating the exact purpose the adapter's own comment states ("the
    mock's exact key"). It stayed dormant because the index holds conditions 5
    and 6, and it was invisible from either provider alone.

    Two digits are the whole point of the fixture: with 5 and 6 the two sort
    keys agree and this test cannot fail.
    """
    office_roster([_sem_row()])
    cond10 = {**RAW_HIT["beam_condition"], "SEM_Cond_No": 10}
    cond5 = {**RAW_HIT["beam_condition"], "SEM_Cond_No": 5}
    _capture(monkeypatch, hits=[_hit(beam_condition=cond10), _hit(beam_condition=cond5)])
    docs = office.build_network_sharpness_docs(
        "MCD018", None, ANCHOR - timedelta(days=5), ANCHOR
    )

    office_order = [d["beam_condition"]["SEM_Cond_No"] for d in docs]
    assert office_order == [5, 10]
    assert office_order == sorted(office_order)  # i.e. what the mock produces


def test_build_raises_when_the_result_fills_the_cap(monkeypatch, office_roster):
    # ~250 docs per tool per 30-day window is the sizing assumption; filling a
    # 10_000 cap means it broke, and a truncated history drawn as a complete
    # one is unfalsifiable from the chart.
    office_roster([_sem_row()])
    _capture(monkeypatch, hits=[RAW_HIT] * office.MAX_SHARPNESS_DOCS)
    with pytest.raises(LookupError, match="cap"):
        office.build_network_sharpness_docs(
            "MCD018", None, ANCHOR - timedelta(days=30), ANCHOR
        )


def test_build_returns_an_empty_list_for_a_cdsem_tool_that_logged_nothing(
    monkeypatch, office_roster
):
    # `sharpness` IS in CDSEM_ONLY_SERVICES, so service_gate turns HV-SEM tools
    # away upstream and this adapter only ever sees CD-SEMs. That makes an
    # empty pull unambiguous: the tool simply logged nothing in the window.
    office_roster([_sem_row()])
    _capture(monkeypatch)
    assert office.build_network_sharpness_docs(
        "MCD018", None, ANCHOR - timedelta(days=30), ANCHOR
    ) == []


# ───────────────────── dispatcher → contract, office path ───────────────────

def test_office_sharpness_payload_matches_the_hardware_contract(
    monkeypatch, office_roster
):
    """The whole office sharpness path — adapter plus normalizer — vs the contract.

    Wires the tracked template in as if `sharpness/office.py` had been copied,
    with the roster and `fetch_hits` faked, so the branch that only ever runs
    at the office is exercised at home.
    """
    office_roster([_sem_row()])
    _capture(monkeypatch, hits=[RAW_HIT])
    real_import = dispatcher.import_module

    def fake_import(name):
        return office if name.endswith(".sharpness.office") else real_import(name)

    monkeypatch.setattr(dispatcher, "import_module", fake_import)
    payload = dispatcher.get_hardware_service(
        "cdsem", "sharpness", "MCD018", "M16A", ANCHOR - timedelta(days=14), ANCHOR
    )

    assert_matches(payload, HardwarePayload)
    # docs_payload's discriminated-by-service convention: sharpness populates
    # `docs` and never `settings`. The frontend branches on which is present.
    assert payload["docs"] == [RAW_HIT]
    assert "settings" not in payload
    # The fab label comes from the payload, not the docs — the index has none.
    assert payload["fab_name"] == "M16A"


def test_hvsem_never_reaches_the_office_adapter_at_all(monkeypatch):
    """`service_gate` turns HV-SEM away before any adapter or roster is touched.

    Pinned from the office side specifically: HV-SEM "TP"-series tools are
    HITACHI and perfectly real, they simply have no chamber-stub monitor. If
    the gate ever moved below the dispatch, this adapter would try to resolve
    an IP for them and raise a roster error on a tool that is fine.
    """
    def explode(name):
        raise AssertionError(f"no tab module may be imported for hvsem ({name})")

    monkeypatch.setattr(dispatcher, "import_module", explode)
    payload = dispatcher.get_hardware_service(
        "hvsem", "sharpness", "TP0001", "M16A", ANCHOR - timedelta(days=14), ANCHOR
    )

    assert_matches(payload, HardwarePayload)
    assert payload["available"] is False
    assert "CD-SEM" in payload["summary"]
