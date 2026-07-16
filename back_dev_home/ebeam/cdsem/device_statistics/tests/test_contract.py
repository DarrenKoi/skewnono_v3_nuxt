"""Contract gate for device_statistics. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/cdsem/device_statistics
Office: SKEWNONO_DEVICE_STATISTICS_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/cdsem/device_statistics
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.cdsem.device_statistics import data
from back_dev_home.ebeam.cdsem.device_statistics.contracts import (
    DeviceDescRow,
    R3DeviceGrpRow,
    RecipeParamsRow,
    RuleVersion,
    TrendBucket,
)


def _sample_lot_cd() -> str:
    """A real lot code, derived from live data rather than hardcoded — keeps
    the test provider-independent (mock and office won't share lot codes)."""
    rows = data.get_r3_device_grp()
    assert rows, "expected at least one r3_device_grp row to derive a sample lot_cd"
    return rows[0]["lot_cd"]


def test_r3_device_grp_matches_contract():
    rows = data.get_r3_device_grp()
    assert rows
    assert_matches(rows, list[R3DeviceGrpRow])


def test_device_desc_matches_contract():
    rows = data.get_device_desc()
    assert rows
    assert_matches(rows, list[DeviceDescRow])


def test_recipe_params_matches_contract():
    # Narrowed to a single lot_cd — an unfiltered call fans out over every
    # known lot (thousands) and is not a real usage pattern; the frontend
    # always joins a user-selected lot list before calling. See MIGRATION.md.
    lot_cd = _sample_lot_cd()
    rows = data.get_recipe_params([lot_cd])
    assert rows
    assert_matches(rows, list[RecipeParamsRow])


def test_weekly_trend_data_matches_contract():
    # Same narrowing rationale as recipe_params above.
    lot_cd = _sample_lot_cd()
    trend = data.get_weekly_trend_data([lot_cd])
    assert trend
    assert_matches(trend, dict[str, TrendBucket])


def test_rules_matches_contract():
    rules = data.get_rules("R3")
    assert rules is not None
    assert_matches(rules, RuleVersion)


def test_rules_unknown_fab_returns_none():
    assert data.get_rules("does-not-exist") is None
