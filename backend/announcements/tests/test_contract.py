"""Contract gate for announcements. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest backend/announcements
Office: SKEWNONO_ANNOUNCEMENTS_PROVIDER=office .venv/bin/pytest backend/announcements

Nothing here is fenced behind the provider: the only assertion is the contract
check itself (which pins the required id/level/title/body keys and the level
enum), and "no active announcements" is a valid empty response in both phases
(MIGRATION.md) — so there is no mock-only invariant to keep out of the office run.
"""

from backend._core.contract_check import assert_matches
from backend.announcements import data
from backend.announcements.contracts import AnnouncementsResponse


def test_get_announcements_matches_contract():
    assert_matches(data.get_announcements(), AnnouncementsResponse)
