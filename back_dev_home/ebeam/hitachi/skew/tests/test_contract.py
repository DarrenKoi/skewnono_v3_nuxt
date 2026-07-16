"""Contract gate for skew. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/skew
Office: SKEWNONO_SKEW_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/skew
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.skew import data
from back_dev_home.ebeam.hitachi.skew.contracts import SkewCheckPayload


def test_skew_check_matches_contract():
    payload = data.get_skew_check("cdsem", "R3", None)
    assert_matches(payload, SkewCheckPayload)
