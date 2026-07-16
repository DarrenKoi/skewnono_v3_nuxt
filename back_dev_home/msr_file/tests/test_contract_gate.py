"""Provider-independent contract gate for msr_file (runs via data.py).

The sibling test_contract.py intentionally pins MOCK-ONLY invariants and
imports providers.mock directly - do not merge these files.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.msr_file import data
from back_dev_home.msr_file.contracts import MsrFileResponse


# The four canonical metadata keys the office source MUST emit to unlock the
# layout-dependent analyses. They are NotRequired on the shared contract (mock
# intentionally omits them), so the office gate below enforces them explicitly
# in office mode instead of letting an office payload omit them and still pass.
_OFFICE_GATED_KEYS = (
    "site_layout_hash",
    "recipe_revision",
    "coordinate_transform_version",
    "sequence_timestamp",
)


def test_msr_file_matches_contract():
    result = data.get_msr_file("MSR-CONTRACT-0001", "ADI", 40)
    assert result is not None
    assert_matches(result, MsrFileResponse)


def test_office_emits_gated_metadata():
    if get_data_provider("msr_file") != "office":
        pytest.skip("layout metadata is only required of the office provider")
    result = data.get_msr_file("MSR-CONTRACT-0001", "ADI", 40)
    assert result is not None
    exe = result["exe_detail_info"]
    missing = [key for key in _OFFICE_GATED_KEYS if not exe.get(key)]
    assert not missing, f"office must emit layout metadata keys: {missing}"
