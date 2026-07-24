"""Reso Center (`category: "reso_center_log"`) mock shape tests.

Pins the flat field contract after Focus Sweep removal: the doc carries exactly
the 13 scalar/metadata fields — none of the wide `Resolution_Range*` sweep
objects, no `fdc_category` — and `ResoDelta` is the derived difference
`ResoIScenter - BestReso` (>= 0), not an independent random value.
"""

from datetime import datetime, timedelta

from back_dev_home.ebeam.hitachi.hardware.providers.reso_center import mock


ANCHOR = datetime(2026, 5, 20, 9, 0)

EXPECTED_FIELDS = {
    "category",
    "CenterX",
    "CenterY",
    "BestReso",
    "ResoIScenter",
    "ResoDelta",
    "beam_condition",
    "timestamp",
    "timestamp_date",
    "eqp_ip",
    "eqp_id",
    "fac_id",
    "fab_name",
}

REMOVED_FIELDS = {
    "Resolution_Range",
    "Resolution_Range_Raw",
    "Resolution_Range_Smooth",
    "fdc_category",
}


def _docs():
    docs = mock.build_reso_center_docs("CDX001", "R3", ANCHOR - timedelta(days=14), ANCHOR)
    assert docs, "mock produced no reso_center docs for the window"
    return docs


def test_docs_carry_exactly_the_flat_field_set():
    for doc in _docs():
        assert set(doc) == EXPECTED_FIELDS
    # And explicitly: none of the dropped sweep objects / fdc_category linger.
    for doc in _docs():
        assert REMOVED_FIELDS.isdisjoint(doc)


def test_resodelta_is_iscenter_minus_bestreso_and_non_negative():
    for doc in _docs():
        assert doc["ResoDelta"] == round(doc["ResoIScenter"] - doc["BestReso"], 2)
        assert doc["ResoDelta"] >= 0
