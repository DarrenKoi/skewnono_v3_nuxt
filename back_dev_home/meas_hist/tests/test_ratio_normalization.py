"""Regression tests for measurement-history ratio normalization.

The derivation lives in `providers/_shared.py` and is applied by each adapter,
not by `data.py` — the dispatcher stays a dispatcher. These tests therefore
pin the shared helper directly, plus the invariant it exists to guarantee on
real mock rows.
"""

import pytest

from back_dev_home.meas_hist.data import get_meas_hist
from back_dev_home.meas_hist.providers._shared import derive_fail_ratio


def test_derives_fail_ratio_from_image_counts():
    # The source's own fail_ratio is ignored; 10/40 is the answer even when
    # the index reports 25.0 (a percentage where a fraction is expected).
    assert derive_fail_ratio(fail_images=10, total_images=40) == pytest.approx(0.25)


def test_caps_impossible_fail_ratio_at_one():
    assert derive_fail_ratio(fail_images=50, total_images=40) == 1.0


def test_zero_total_images_yields_zero_not_a_division_error():
    assert derive_fail_ratio(fail_images=0, total_images=0) == 0.0


def test_negative_fail_count_floors_at_zero():
    assert derive_fail_ratio(fail_images=-5, total_images=40) == 0.0


def test_mock_rows_carry_a_ratio_consistent_with_their_counts():
    rows = get_meas_hist()["rows"]
    assert rows, "mock provider returned no rows to check"
    for row in rows:
        assert 0.0 <= row["fail_ratio"] <= 1.0
        assert row["fail_ratio"] == derive_fail_ratio(
            row["fail_images"], row["total_images"]
        )
