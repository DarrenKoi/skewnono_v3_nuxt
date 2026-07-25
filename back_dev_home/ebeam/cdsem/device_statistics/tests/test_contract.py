"""Contract gate for device_statistics. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/cdsem/device_statistics
Office: SKEWNONO_DEVICE_STATISTICS_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/cdsem/device_statistics

providers/office_example.py is still a stub, so the office command above fails
with its NotImplementedError rather than a contract violation — that is the
adapter being unwritten, not this gate being wrong.

This is the one feature of the seven that legitimately keys on `fac_id` rather
than `fab_name` (MIGRATION.md), and the join across r3_device_grp /
device_desc / recipe_params has to hold under either provider — that is
asserted unfenced. What is NOT provider-independent is that the tables have
ROWS at all: the mock fabricates them from a fixed RNG seed, while the office
source can return nothing for a lot list. Those assumptions are fenced behind
get_data_provider("device_statistics") == "mock", and the lookups that need a
sample row skip instead of failing when the active provider has none.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.cdsem.device_statistics import data
from back_dev_home.ebeam.cdsem.device_statistics.contracts import (
    DeviceDescRow,
    R3DeviceGrpRow,
    RecipeParamsRow,
    RuleVersion,
    TrendBucket,
)


def _is_mock() -> bool:
    return get_data_provider("device_statistics") == "mock"


def _sample_lot_cd() -> str:
    """A real lot code, derived from live data rather than hardcoded.

    The mock's r3_device_grp is generated from a fixed RNG seed and always has
    rows; an office source can return none, and there is then no lot_cd to key
    the recipe/trend lookups off.
    """
    rows = data.get_r3_device_grp()
    if not rows:
        pytest.skip("active provider returned no r3_device_grp rows")
    return rows[0]["lot_cd"]


def test_r3_device_grp_matches_contract():
    rows = data.get_r3_device_grp()
    assert_matches(rows, list[R3DeviceGrpRow])
    if _is_mock():
        # Fixed RNG seed (20260426) — an empty table means the generator broke.
        assert rows, "mock r3_device_grp must not be empty"


def test_device_desc_matches_contract():
    rows = data.get_device_desc()
    assert_matches(rows, list[DeviceDescRow])
    if _is_mock():
        # Same fabricated source as r3_device_grp above.
        assert rows, "mock device_desc must not be empty"


def test_recipe_params_matches_contract():
    # Narrowed to a single lot_cd — an unfiltered call fans out over every
    # known lot (thousands) and is not a real usage pattern; the frontend
    # always joins a user-selected lot list before calling. See MIGRATION.md.
    lot_cd = _sample_lot_cd()
    rows = data.get_recipe_params([lot_cd])
    assert_matches(rows, list[RecipeParamsRow])

    # The lot_cd filter is the join key the whole feature is built on
    # (MIGRATION.md: fac_id/lot_cd must stay joinable across all three tables).
    # A row for a lot nobody asked for would land in the wrong device panel.
    for row in rows:
        assert row["lot_cd"] == lot_cd
        assert all(param["point_count"] >= 0 for param in row["parameters"])

    if _is_mock():
        # Every mock lot has fabricated recipes behind it; a real lot can have
        # no recipe rows yet.
        assert rows, "mock recipe_params must not be empty for a known lot"


def test_weekly_trend_data_matches_contract():
    # Same narrowing rationale as recipe_params above.
    lot_cd = _sample_lot_cd()
    trend = data.get_weekly_trend_data([lot_cd])
    assert_matches(trend, dict[str, TrendBucket])

    # Whatever the source, every summary row in a bucket must belong to the
    # lot that was asked for — the route keys the chart series off it.
    for bucket in trend.values():
        for summary in bucket["all_summary"]:
            assert summary["lot_cd"] == lot_cd
            assert summary["avail_recipe"] <= summary["total_recipe"]

    if _is_mock():
        # Byte-identical per (lot_cd, date_index) from the seeded generator, so
        # an empty trend means it broke. An office lot can have no history.
        assert trend, "mock weekly trend must not be empty for a known lot"


def test_rules_matches_contract():
    rules = data.get_rules("R3")
    if _is_mock():
        # Mock-only: providers/rules.py ships exactly one seeded fab. Office
        # may serve more than one fab and more than one version (MIGRATION.md),
        # and R3 having no published rule version there is not a failure.
        assert rules is not None, "the mock rule seed must ship an R3 version"
    if rules is None:
        pytest.skip("active provider serves no rule version for R3")

    assert_matches(rules, RuleVersion)
    assert rules["thresholds"]["yellow_at"] <= rules["thresholds"]["red_at"]
    # ruleEngine.selectorMatches does first-match selection over `cells`, so a
    # duplicated cell id makes which rule wins depend on load order.
    ids = [cell["id"] for cell in rules["cells"]]
    assert len(set(ids)) == len(ids), "rule cell ids must be unique"


def test_rules_unknown_fab_returns_none():
    # Provider-independent: the route turns None into a 404, so an unknown fab
    # must never resolve to some other fab's caps.
    assert data.get_rules("does-not-exist") is None
