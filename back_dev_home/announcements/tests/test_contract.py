"""Contract gate for announcements. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/announcements
Office: SKEWNONO_ANNOUNCEMENTS_PROVIDER=office .venv/bin/pytest back_dev_home/announcements
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.announcements import data
from back_dev_home.announcements.contracts import AnnouncementsResponse


def test_get_announcements_matches_contract():
    assert_matches(data.get_announcements(), AnnouncementsResponse)
