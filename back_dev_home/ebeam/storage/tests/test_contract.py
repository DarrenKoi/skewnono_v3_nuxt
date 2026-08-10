"""Contract gate for storage. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/storage
Office: SKEWNONO_STORAGE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/storage
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.storage import data
from back_dev_home.ebeam.storage.contracts import (
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
    if get_data_provider("storage") == "mock":
        # Only the mock guarantees data; an empty office fleet is contract-valid.
        assert fab_names, "mock fleet should expose at least one fab_name"
    if not fab_names:
        return

    target = sorted(fab_names)[0]
    filtered = data.get_storage("cdsem", [target])
    assert filtered, f"expected rows for fab_name {target!r}"
    assert {row["fab_name"] for row in filtered} == {target}
    # A filter matching one fab_name must not leak sibling fabs under the same fac.
    assert len(filtered) < len(everything) or len(fab_names) == 1


def test_ppid_unavailable_never_emits_a_row_without_an_equipment():
    """로스터에 없는 IP 는 신호가 아니라 사내 DB 의 찌꺼기입니다.

    user-confirmed 2026-08-10. office 어댑터는 sem_list 매칭이 없으면 행을
    버리는데 mock 은 일부러 고아 IP 3개를 만들어 eqp_id="" 행으로 내보냈고,
    두 docstring 이 서로 반대 규칙을 선언하고 있었습니다.
    """
    rows = data.get_ppid_unavailable("cdsem")["rows"]
    assert rows, "mock 이 행을 하나도 내지 않았습니다"
    assert all(row["eqp_id"] for row in rows)
    assert all(row["fab_name"] for row in rows)
