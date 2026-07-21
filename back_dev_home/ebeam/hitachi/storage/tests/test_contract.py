"""Contract gate for storage. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/storage
Office: SKEWNONO_STORAGE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/storage
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.storage import data
from back_dev_home.ebeam.hitachi.storage.contracts import (
    PpidUnavailableSnapshot,
    StorageRow,
)


def test_get_storage_matches_contract():
    rows = data.get_storage("cdsem")
    assert_matches(rows, list[StorageRow])


def test_get_ppid_unavailable_matches_contract():
    snapshot = data.get_ppid_unavailable("cdsem")
    assert_matches(snapshot, PpidUnavailableSnapshot)


def test_get_storage_filters_by_fab_name():
    # The left-sidebar selection is a fab_name (M16A, R3, R4), so the filter
    # must match the fab_name column exactly — not collapse to a parent fac_id.
    everything = data.get_storage("cdsem")
    fab_names = {row["fab_name"] for row in everything}
    assert fab_names, "mock fleet should expose at least one fab_name"

    target = sorted(fab_names)[0]
    filtered = data.get_storage("cdsem", [target])
    assert filtered, f"expected rows for fab_name {target!r}"
    assert {row["fab_name"] for row in filtered} == {target}
    # A filter matching one fab_name must not leak sibling fabs under the same fac.
    assert len(filtered) < len(everything) or len(fab_names) == 1
