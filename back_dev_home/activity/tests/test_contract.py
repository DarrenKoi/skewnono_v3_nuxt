"""Contract gate for activity. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/activity
Office: SKEWNONO_ACTIVITY_PROVIDER=office .venv/bin/pytest back_dev_home/activity

Every shape check here runs under both providers. The one mock-only step is the
demo seeding in test_me_and_history_match_contract — data.py wires
``seed_demo_users`` to the mock unconditionally, so it can never populate an
office backend and is fenced accordingly.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.activity import data
from back_dev_home.activity.contracts import (
    FabUsageResponse,
    MeResponse,
    SummaryResponse,
    UserHistoryResponse,
    UserListResponse,
)


def test_summary_matches_contract():
    assert_matches(data.get_summary(), SummaryResponse)


def test_fab_page_usage_matches_contract():
    assert_matches(data.get_fab_page_usage(), FabUsageResponse)


def test_users_list_matches_contract():
    assert_matches(data.get_users_list(), UserListResponse)


def test_me_and_history_match_contract():
    if get_data_provider("activity") == "mock":
        # Seed demo users so the mock run is self-sufficient. Mock-only by
        # design: data.py re-exports seed_demo_users unswitched, so calling it
        # under office would seed an in-memory store nothing then reads.
        data.seed_demo_users()
    users = data.get_users_list()["users"]
    if not users:
        # A freshly-connected office backend may legitimately have recorded no
        # users yet (MIGRATION.md), so there is nothing to exercise
        # get_me()/history against.
        pytest.skip("active provider returned no users")
    user_id = users[0]["user_id"]
    assert_matches(data.get_me(user_id), MeResponse)

    # The id came out of get_users_list, so it is a KNOWN user — get_user_history
    # returns None only for unknown ids. Asserting instead of skipping on None
    # keeps a lookup that never resolves from passing the gate.
    history = data.get_user_history(user_id)
    assert history is not None, f"a listed user ({user_id}) must have history"
    assert_matches(history, UserHistoryResponse)
