"""Contract gate for hardware. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/hardware
Office: SKEWNONO_HARDWARE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/hardware
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.hardware import data
from back_dev_home.ebeam.hitachi.hardware.contracts import (
    VALID_SERVICES,
    HardwarePayload,
)
from back_dev_home.ebeam.hitachi.hardware.providers import office_example


@pytest.mark.parametrize("service", sorted(VALID_SERVICES))
def test_hardware_service_matches_contract(service):
    # Exercise every service (bsm/reso-center/fdc/mdc/sce/bm-pm/sharpness) with
    # a concrete equipment id, not just the empty bsm path — each service has
    # its own docs/settings/availability shape that must satisfy the contract.
    end = datetime(2026, 5, 20, 9, 0)
    start = end - timedelta(days=14)
    payload = data.get_hardware_service("cdsem", service, "CDX001", "R3", start, end)
    assert_matches(payload, HardwarePayload)


# --- office dispatcher tab fallback ---------------------------------------
#
# These exercise the TRACKED template (`office_example`), never the gitignored
# `providers/office.py`, so they run identically at home and at the office.
#
# They must also stay correct at EVERY stage of the migration: a tab gains an
# `office.py` the moment it is wired, and from then on it no longer falls back
# and needs live OPENSEARCH_*/Redis config to run at all. So each case skips
# for tabs that are already connected rather than asserting a state that
# expires — otherwise wiring `fdc` would turn this suite red at the office.

TABS = ["fdc", "sharpness", "bm_pm", "bsm", "reso_center", "mdc", "sce"]

_PROVIDERS_DIR = Path(office_example.__file__).parent


def _is_wired(tab: str) -> bool:
    return (_PROVIDERS_DIR / tab / "office.py").exists()


def _unwired_tab() -> str:
    """Any tab still on mock, for tests that need a fallback to observe."""
    for tab in TABS:
        if not _is_wired(tab):
            return tab
    pytest.skip("every hardware tab is wired; no fallback left to exercise")


@pytest.mark.parametrize("tab", TABS)
def test_tab_falls_back_to_mock_when_office_absent(tab):
    # A tab with no office.py must serve its own mock module rather than
    # raising, so one unconnected tab cannot break the whole hardware page.
    if _is_wired(tab):
        pytest.skip(f"{tab} has an office.py — nothing to fall back to")
    module = office_example._tab(tab)
    assert module.__name__.endswith(f".{tab}.mock")


def test_tab_fallback_logs_which_tab_went_mock(caplog):
    # The response carries no "mock ·" marker by design, so this log line is
    # the only signal distinguishing a real office tab from a fallback.
    tab = _unwired_tab()
    with caplog.at_level("INFO", logger=office_example.__name__):
        office_example._tab(tab)
    assert f"hardware/{tab}" in caplog.text
    assert "MOCK" in caplog.text


@pytest.mark.parametrize("service", sorted(VALID_SERVICES))
def test_office_dispatcher_serves_unconnected_services_from_mock(service):
    # The state the office starts in: SKEWNONO_HARDWARE_PROVIDER=office with
    # nothing wired yet. Every not-yet-connected service must still satisfy the
    # contract through its mock fallback — this is what keeps the page usable
    # during the step-by-step migration, and it is the check that would have
    # caught the old fail-fast dispatcher breaking six tabs at once.
    if _is_wired(service.replace("-", "_")):
        pytest.skip(f"{service} is wired; covered by the office contract gate")
    end = datetime(2026, 5, 20, 9, 0)
    start = end - timedelta(days=14)
    payload = office_example.get_hardware_service(
        "cdsem", service, "CDX001", "R3", start, end
    )
    assert_matches(payload, HardwarePayload)


def test_broken_tab_adapter_propagates_instead_of_falling_back(monkeypatch):
    # The failure this design is most exposed to: a WIRED adapter whose import
    # blows up (missing ops_store, bad import line) silently degrading to mock
    # and serving fabricated data under an office switch. Only the tab module's
    # own absence may fall back.
    real_import = office_example.import_module

    def fake_import(name):
        if name.endswith(".fdc.office"):
            raise ModuleNotFoundError("No module named 'ops_store'", name="ops_store")
        return real_import(name)

    monkeypatch.setattr(office_example, "import_module", fake_import)
    with pytest.raises(ModuleNotFoundError, match="ops_store"):
        office_example._tab("fdc")
