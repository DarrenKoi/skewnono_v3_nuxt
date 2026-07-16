"""Provider-independent contract gate for msr_file (runs via data.py).

The sibling test_contract.py intentionally pins MOCK-ONLY invariants and
imports providers.mock directly - do not merge these files.
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.msr_file import data
from back_dev_home.msr_file.contracts import MsrFileResponse


def test_msr_file_matches_contract():
    result = data.get_msr_file("MSR-CONTRACT-0001", "ADI", 40)
    assert result is not None
    assert_matches(result, MsrFileResponse)
