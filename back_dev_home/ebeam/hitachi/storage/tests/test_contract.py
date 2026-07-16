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
