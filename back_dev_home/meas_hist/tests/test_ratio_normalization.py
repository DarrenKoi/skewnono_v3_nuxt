"""Regression tests for measurement-history ratio scale.

`fail_ratio` is a PERCENTAGE, 0..100, because that is what the office
OpenSearch documents store and the office value is authoritative. The scale
lives in `providers/_shared.py` and is applied by each adapter, not by
`data.py` — the dispatcher stays a dispatcher.

The bug these pin: a 0..1 fraction here plus a renderer that multiplies by
100 (or the reverse) is off by 100x, and 4.57 rendered as "457.0%" is how
that reaches a user looking like data rather than a defect.
"""

import pytest

from back_dev_home.meas_hist.data import get_meas_hist
from back_dev_home.meas_hist.providers._shared import (
    fail_ratio_percent,
    normalize_fail_ratio,
)


def test_ratio_is_a_percentage_not_a_fraction():
    # 10 of 40 images failed. 25 percent — not 0.25.
    assert fail_ratio_percent(fail_images=10, total_images=40) == pytest.approx(25.0)


def test_a_small_ratio_stays_readable_at_percent_scale():
    assert fail_ratio_percent(fail_images=15, total_images=328) == pytest.approx(4.5732)


def test_zero_total_images_yields_zero_not_a_division_error():
    assert fail_ratio_percent(fail_images=0, total_images=0) == 0.0


def test_stored_ratio_is_read_as_is():
    """The office field is authoritative — no conversion, no re-derivation."""
    assert normalize_fail_ratio(4.57) == 4.57
    assert normalize_fail_ratio("4.57") == 4.57


def test_impossible_stored_ratio_is_clamped_to_one_hundred():
    """A value above 100 is not a ratio. Clamping keeps a scale mismatch from
    rendering as a plausible-looking "457.0%" instead of an obvious error."""
    assert normalize_fail_ratio(457.0) == 100.0
    assert normalize_fail_ratio(-5) == 0.0


def test_missing_or_unparseable_stored_ratio_is_zero_not_a_crash():
    assert normalize_fail_ratio(None) == 0.0
    assert normalize_fail_ratio("") == 0.0
    assert normalize_fail_ratio(float("nan")) == 0.0


def test_mock_rows_carry_a_percent_ratio_consistent_with_their_counts():
    rows = get_meas_hist()["rows"]
    assert rows, "mock provider returned no rows to check"
    for row in rows:
        assert 0.0 <= row["fail_ratio"] <= 100.0
        assert row["fail_ratio"] == fail_ratio_percent(
            row["fail_images"], row["total_images"]
        )


def test_some_mock_rows_exceed_one_so_a_fraction_bug_cannot_hide():
    """A suite where every ratio happens to be under 1.0 would pass either
    way. Assert the mock actually exercises the percent range."""
    rows = get_meas_hist()["rows"]
    assert any(row["fail_ratio"] > 1.0 for row in rows)
