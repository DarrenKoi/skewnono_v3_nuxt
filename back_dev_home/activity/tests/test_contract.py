"""Contract gate for activity. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/activity
Office: SKEWNONO_ACTIVITY_PROVIDER=office .venv/bin/pytest back_dev_home/activity
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
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
    # Seed demo users to ensure the test is self-sufficient and
    # provider-independent (office has different users than mock).
    data.seed_demo_users()
    users = data.get_users_list()["users"]
    if not users:
        # seed_demo_users only seeds the mock store; a freshly-connected office
        # provider may legitimately return no users, so there is nothing to
        # exercise get_me()/history against.
        pytest.skip("active provider returned no users")
    user_id = users[0]["user_id"]
    assert_matches(data.get_me(user_id), MeResponse)
    history = data.get_user_history(user_id)
    if history is not None:
        assert_matches(history, UserHistoryResponse)
