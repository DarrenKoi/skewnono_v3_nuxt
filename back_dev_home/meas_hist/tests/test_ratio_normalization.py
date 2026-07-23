"""Regression tests for measurement-history ratio normalization."""

import pytest

from back_dev_home.meas_hist import data


class _Provider:
    def __init__(self, total_images: int, fail_images: int, fail_ratio: float):
        self.row = {
            "msr": "MSR-RATIO-001",
            "total_images": total_images,
            "fail_images": fail_images,
            "fail_ratio": fail_ratio,
        }

    def get_meas_hist(self, *_args):
        return {
            "tool_type": "cd-sem",
            "fab_name": "M11",
            "recipe_name": "ADI_CD_BIAS_001",
            "total": 1,
            "rows": [self.row],
        }


def test_get_meas_hist_derives_fail_ratio_from_image_counts(monkeypatch):
    provider = _Provider(total_images=40, fail_images=10, fail_ratio=25.0)
    monkeypatch.setattr(data, "_provider", lambda: provider)

    response = data.get_meas_hist()

    assert response["rows"][0]["fail_ratio"] == pytest.approx(0.25)


def test_get_meas_hist_caps_impossible_fail_ratio_at_one(monkeypatch):
    provider = _Provider(total_images=40, fail_images=50, fail_ratio=1.25)
    monkeypatch.setattr(data, "_provider", lambda: provider)

    response = data.get_meas_hist()

    assert response["rows"][0]["fail_ratio"] == 1.0
