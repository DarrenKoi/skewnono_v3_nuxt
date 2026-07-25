"""Office MDC adapter tests.

These exercise the TRACKED template (`mdc/office_example`), never the
gitignored `mdc/office.py`, and never touch a cluster: every test either calls
the template directly or hands the dispatcher a fabricated tab module. A test
here that takes measurable time has opened a socket and is wrong.

`mdc/office_example.py` is still a STUB — both builders raise
`NotImplementedError` (hardware/MIGRATION.md lists it as such). So unlike the
FDC and sharpness suites there is no mapping logic to feed documents to yet,
and pretending otherwise would just pin an empty file. What IS pinnable, and
what this file pins, is everything the eventual implementation has to land
inside:

* the refusal itself — a stub must raise, never return `{}` or `[]`, because
  an empty settings snapshot renders as "this tool has no MDC calibration"
  rather than as "nobody wired this yet";
* the call shape the dispatcher uses — both builders are called
  POSITIONALLY, and `build_mdc_history` takes no `fab_name` while
  `build_mdc_settings` does. An implementation that "helpfully" adds a fab
  argument to history breaks at the office and nowhere else;
* which window bound becomes the as-of date (`end`, not `start`);
* the raw shapes the two builders must return, pinned against `mdc/mock.py`
  and against `HardwarePayload` — "resemble the mock" meaning the contract
  shape, never the mock's fabricated numbers.

Together these are the checks that would have caught the two mistakes an
office implementation of this tab is most likely to make: returning a wide
per-condition record instead of the long format the 시계열 sub-tab reads, and
dropping the in-fab siblings the 비교 sub-tab exists for.
"""

import inspect
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload
from back_dev_home.ebeam.hitachi.hardware.normalizers import CDSEM_ONLY_SERVICES
from back_dev_home.ebeam.hitachi.hardware.providers import office_example as dispatcher
from back_dev_home.ebeam.hitachi.hardware.providers.mdc import (
    mock,
    office_example as office,
)


ANCHOR = datetime(2026, 5, 20, 9, 0)
START = ANCHOR - timedelta(days=14)

BUILDERS = ("build_mdc_settings", "build_mdc_history")

# An office-shaped return for each builder: the SHAPE the adapter must produce,
# with values that are obviously not the mock's (the mock's per-tool random
# walk is a Phase-1 fabrication and must never be asserted as an office
# property). Correction factors sit near 1.0 because `result = MDC * raw`.
OFFICE_SETTINGS = {
    "ECDX100": {"800V_HR_0Deg": "1.000431", "800V_HR_90Deg": "0.998210"},
    "ECDX214": {"800V_HR_0Deg": "1.002007", "800V_HR_90Deg": "1.000004"},
}
OFFICE_HISTORY = [
    {"timestamp": "2026-05-11 04:00", "beam_condition": "800V_HR_0Deg",
     "mdc_value": 1.000102},
    {"timestamp": "2026-05-11 04:00", "beam_condition": "800V_HR_90Deg",
     "mdc_value": 0.999318},
    {"timestamp": "2026-05-18 07:00", "beam_condition": "800V_HR_0Deg",
     "mdc_value": 1.000431},
    {"timestamp": "2026-05-18 07:00", "beam_condition": "800V_HR_90Deg",
     "mdc_value": 0.998210},
]


# ──────────────────────────── the stub's refusal ────────────────────────────

@pytest.mark.parametrize("builder", BUILDERS)
def test_the_stub_refuses_by_name_rather_than_returning_empty_data(builder):
    """An unwired builder must raise, and say which builder and where to look.

    The alternative — returning `{}` / `[]` — is the failure mode this whole
    per-tab design is meant to avoid: the tab renders successfully, shows no
    calibration, and an engineer concludes the tool has none. Only the ABSENCE
    of `mdc/office.py` may fall back to mock (pinned in test_contract.py);
    a present-but-unimplemented adapter must fail loudly.
    """
    args = {
        "build_mdc_settings": ("ECDX100", "M16A", ANCHOR),
        "build_mdc_history": ("ECDX100", START, ANCHOR),
    }[builder]
    with pytest.raises(NotImplementedError) as excinfo:
        getattr(office, builder)(*args)

    message = str(excinfo.value)
    assert builder in message
    assert "MIGRATION.md" in message


# ───────────────────── the call shape the office must fit ───────────────────

@pytest.mark.parametrize("builder", BUILDERS)
def test_template_and_mock_take_the_same_parameters_in_the_same_order(builder):
    # The dispatcher calls both builders POSITIONALLY, so parameter ORDER is
    # the real contract and a rename is free. Compared name-by-name rather than
    # by `Signature` equality because mock.py uses `from __future__ import
    # annotations` and the template does not — their annotation OBJECTS differ
    # while their call shapes are identical.
    def names(fn):
        return list(inspect.signature(fn).parameters)

    assert names(getattr(office, builder)) == names(getattr(mock, builder))


def test_history_takes_no_fab_argument_while_settings_does():
    """The asymmetry an office implementation is most likely to "fix".

    Settings compares the selected tool against its in-fab siblings, so it
    needs the fab. History is the selected tool's own calibration series —
    scoping it by fab again could only subtract, and a stale fab label would
    empty the 시계열 chart with no error. Adding the argument also breaks the
    dispatcher's positional call outright.
    """
    assert "fab_name" in inspect.signature(office.build_mdc_settings).parameters
    assert "fab_name" not in inspect.signature(office.build_mdc_history).parameters
    assert list(inspect.signature(office.build_mdc_history).parameters) == [
        "eqp_id", "start", "end"
    ]


def test_the_template_exports_exactly_the_builders_the_dispatcher_calls():
    # A builder the dispatcher does not call is dead code at the office; one it
    # calls but the template omits is an AttributeError on the first request.
    # Nothing else checks this for a per-tab adapter: `tests/_office_state.py`
    # validates fakes against a feature's template, but the per-tab modules are
    # deliberately kept out of the global office registry, so its helpers
    # cannot reach `hardware/providers/mdc/` at all.
    defined = {
        name for name, value in vars(office).items()
        if inspect.isfunction(value)
        and value.__module__ == office.__name__
        and not name.startswith("_")
    }
    assert defined == set(BUILDERS)
    assert set(BUILDERS) == set(mock.__all__)


# ──────────────── dispatcher routing + normalization to contract ────────────

def _wire(monkeypatch, **functions):
    """Wire a fabricated `mdc/office.py` into the dispatcher for one test."""
    module = SimpleNamespace(**functions)
    real_import = dispatcher.import_module

    def fake_import(name):
        return module if name.endswith(".mdc.office") else real_import(name)

    monkeypatch.setattr(dispatcher, "import_module", fake_import)


def test_dispatcher_routes_the_window_end_to_settings_and_the_span_to_history(
    monkeypatch,
):
    # The 비교 sub-tab is an as-of SNAPSHOT and the 시계열 sub-tab is a span;
    # both come from one request. Passing `start` as the as-of date would show
    # a two-week-old snapshot next to an up-to-date trend and look like skew.
    seen = {}

    def settings(eqp_id, fab_name, as_of):
        seen["settings"] = (eqp_id, fab_name, as_of)
        return OFFICE_SETTINGS

    def history(eqp_id, start, end):
        seen["history"] = (eqp_id, start, end)
        return OFFICE_HISTORY

    _wire(monkeypatch, build_mdc_settings=settings, build_mdc_history=history)
    payload = dispatcher.get_hardware_service(
        "cdsem", "mdc", "ECDX100", "M16A", START, ANCHOR
    )

    assert seen["settings"] == ("ECDX100", "M16A", ANCHOR)
    assert seen["history"] == ("ECDX100", START, ANCHOR)
    as_of_card = next(c for c in payload["cards"] if c["key"] == "as_of")
    assert as_of_card["value"] == "2026-05-20"


def test_office_mdc_payload_matches_the_hardware_contract(monkeypatch):
    # MDC is the only service besides SCE that populates BOTH optional keys.
    # The frontend branches on their presence, so an office adapter that
    # returned only one would render half a tab without erroring.
    _wire(
        monkeypatch,
        build_mdc_settings=lambda *_: OFFICE_SETTINGS,
        build_mdc_history=lambda *_: OFFICE_HISTORY,
    )
    payload = dispatcher.get_hardware_service(
        "cdsem", "mdc", "ECDX100", "M16A", START, ANCHOR
    )

    assert_matches(payload, HardwarePayload)
    assert payload["settings"] == OFFICE_SETTINGS
    assert payload["docs"] == OFFICE_HISTORY
    assert payload["fab_name"] == "M16A"


def test_sibling_count_is_never_negative_for_a_tool_with_no_in_fab_peers(monkeypatch):
    # A one-tool fab, or an office source that simply has no sibling rows yet,
    # must read "0 동일 fab 장비" — not -1, which the card renders verbatim.
    _wire(
        monkeypatch,
        build_mdc_settings=lambda *_: {"ECDX100": OFFICE_SETTINGS["ECDX100"]},
        build_mdc_history=lambda *_: [],
    )
    payload = dispatcher.get_hardware_service(
        "cdsem", "mdc", "ECDX100", "M16A", START, ANCHOR
    )

    assert_matches(payload, HardwarePayload)
    siblings = next(c for c in payload["cards"] if c["key"] == "sibling_count")
    assert siblings["value"] == 0
    assert payload["docs"] == []  # empty history is a valid answer, not an error


def test_settings_must_key_on_eqp_id_and_carry_the_selected_tool(monkeypatch):
    """The 비교 sub-tab compares by eqp_id, so the selected tool must be a key.

    An office source keyed on anything else — an internal tool number, an IP —
    would render a comparison in which the tool the engineer selected does not
    appear, with every sibling looking equally plausible as "theirs".
    """
    _wire(
        monkeypatch,
        build_mdc_settings=lambda *_: OFFICE_SETTINGS,
        build_mdc_history=lambda *_: OFFICE_HISTORY,
    )
    payload = dispatcher.get_hardware_service(
        "cdsem", "mdc", "ECDX100", "M16A", START, ANCHOR
    )
    assert payload["eqp_id"] in payload["settings"]


# ─────────────── raw shape parity with the mock (contract shape) ────────────
#
# These two compare this file's OFFICE_* fixtures against `mdc/mock.py`. They
# assert nothing about the office adapter — there is none yet — and are not
# meant to: they keep the fixtures the dispatcher tests above are built on
# honest, so a change to the mock's record shape cannot leave those tests
# green while pinning a shape the page no longer reads. They double as the
# written-down target for whoever implements `mdc/office.py`.

def test_office_shaped_settings_match_the_mocks_dict_of_dict_shape():
    # Shape only: {eqp_id: {beam_condition: value}} with STRING values, per
    # docs/datatables/mdc_setting.txt. Values are compared by TYPE, never by
    # magnitude — the mock's numbers are a Phase-1 fabrication.
    reference = mock.build_mdc_settings("ECDX100", "M16A", ANCHOR)

    def shape(settings):
        return {
            type(tool) for tool in settings
        }, {
            (type(cond), type(value))
            for conds in settings.values()
            for cond, value in conds.items()
        }

    assert shape(OFFICE_SETTINGS) == shape(reference) == ({str}, {(str, str)})
    assert len(reference) > 1, "the mock must offer siblings to compare against"


def test_office_shaped_history_matches_the_mocks_long_format_record():
    # LONG format — one record per (timestamp, beam_condition) — not a wide
    # row per timestamp. The 시계열 chart groups by `beam_condition`, so a wide
    # record yields one unnamed series instead of one per condition.
    reference = mock.build_mdc_history("ECDX100", START, ANCHOR)
    assert reference, "the mock must emit history inside a 14-day window"

    assert {frozenset(r) for r in OFFICE_HISTORY} == {frozenset(r) for r in reference}
    assert frozenset(reference[0]) == frozenset(
        {"timestamp", "beam_condition", "mdc_value"}
    )
    for record in (*OFFICE_HISTORY, *reference):
        assert isinstance(record["mdc_value"], float)
        assert isinstance(record["timestamp"], str)


def test_ordering_history_is_the_adapters_job_because_nothing_downstream_sorts(
    monkeypatch,
):
    """`settings_payload` passes `docs` straight through, unsorted.

    Unlike the FDC and sharpness adapters — which re-sort what OpenSearch
    hands them — the MDC office adapter gets no second chance: whatever order
    `build_mdc_history` returns is the order the 시계열 chart plots. Fed a
    deliberately descending history, the payload comes back still descending.
    Pinned as an instruction to the implementer, not as approval: the mock
    emits ascending, so the office builder must too.
    """
    descending = list(reversed(OFFICE_HISTORY))
    _wire(
        monkeypatch,
        build_mdc_settings=lambda *_: OFFICE_SETTINGS,
        build_mdc_history=lambda *_: descending,
    )
    payload = dispatcher.get_hardware_service(
        "cdsem", "mdc", "ECDX100", "M16A", START, ANCHOR
    )
    assert payload["docs"] == descending

    reference = mock.build_mdc_history("ECDX100", START, ANCHOR)
    assert [r["timestamp"] for r in reference] == sorted(
        r["timestamp"] for r in reference
    )


# ─────────────────────────── upstream short-circuits ────────────────────────

def test_mdc_is_not_cdsem_only_so_the_office_adapter_must_serve_hvsem(monkeypatch):
    """HV-SEM tools reach this adapter — unlike bsm / reso-center / sce / sharpness.

    Worth pinning before the office implementation exists, because the natural
    shortcut (query one CD-SEM-shaped source and be done) would silently serve
    nothing for the HV-SEM fleet. Those are the HITACHI "TP"-series tools; they
    have MDC calibration like any other.
    """
    assert "mdc" not in CDSEM_ONLY_SERVICES

    seen = []
    _wire(
        monkeypatch,
        build_mdc_settings=lambda *args: seen.append(args) or OFFICE_SETTINGS,
        build_mdc_history=lambda *_: OFFICE_HISTORY,
    )
    payload = dispatcher.get_hardware_service(
        "hvsem", "mdc", "TP0001", "M16A", START, ANCHOR
    )

    assert seen, "the mdc adapter must be reached for an HV-SEM tool"
    assert_matches(payload, HardwarePayload)
    assert payload["available"] is True


def test_no_tool_selected_short_circuits_before_the_adapter_is_imported(monkeypatch):
    # `service_gate` answers the "pick a tool" state itself, which is why every
    # builder may assume `eqp_id is not None`. If that moved, the office
    # adapter would be handed None and query for the string "None".
    def explode(name):
        raise AssertionError(f"no tab module may be imported without a tool ({name})")

    monkeypatch.setattr(dispatcher, "import_module", explode)
    payload = dispatcher.get_hardware_service(
        "cdsem", "mdc", None, "M16A", START, ANCHOR
    )

    assert_matches(payload, HardwarePayload)
    assert payload["available"] is True
    assert payload["cards"] == [] and payload["tables"] == []
