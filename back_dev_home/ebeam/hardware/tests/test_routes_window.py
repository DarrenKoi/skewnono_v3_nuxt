"""The route's time-window parsing: inbound ISO -> naive KST wall clock.

The office OpenSearch indices store offset-less KST wall clock
(``docs/datatables/README.md``), and every hardware office adapter feeds the
route's datetimes straight into a range clause. So the route is the seam where
an inbound instant has to become a KST wall clock -- and the frontend always
sends an aware UTC instant, because ``new Date().toISOString()`` renders UTC.

These tests pin the CONVERSION. Deleting the ``Z`` instead of converting it
leaves a UTC wall clock wearing a KST label, which slides every window nine
hours into the past; the symptom is the most recent ~9h of data missing from
the tab, with no error anywhere.
"""

from datetime import datetime

from back_dev_home.ebeam.hardware.routes import _parse_iso, _resolve_window
from back_dev_home import create_app


def test_utc_z_instant_becomes_kst_wall_clock():
    # 2026-08-19T20:38Z IS 2026-08-20 05:38 in Seoul. The stored data is
    # labelled with the latter, so that is what the range clause must carry.
    assert _parse_iso("2026-08-19T20:38:00.000Z") == datetime(2026, 8, 20, 5, 38)


def test_z_is_converted_not_deleted():
    # The precise regression: stripping "Z" yields 20:38, nine hours early.
    assert _parse_iso("2026-08-19T20:38:00.000Z") != datetime(2026, 8, 19, 20, 38)


def test_explicit_offset_is_converted_too():
    # Same instant, spelled with a numeric offset instead of Z.
    assert _parse_iso("2026-08-19T20:38:00+00:00") == datetime(2026, 8, 20, 5, 38)


def test_kst_offset_round_trips_to_its_own_wall_clock():
    assert _parse_iso("2026-08-20T05:38:00+09:00") == datetime(2026, 8, 20, 5, 38)


def test_offset_less_value_is_already_kst_and_passes_through():
    # A hand-built deep link carries no offset; it is already a KST wall clock
    # and must not be shifted a second time.
    assert _parse_iso("2026-08-20T05:38:00") == datetime(2026, 8, 20, 5, 38)


def test_unparsable_value_falls_back_to_none():
    assert _parse_iso("not-a-date") is None
    assert _parse_iso("") is None
    assert _parse_iso(None) is None


def test_resolve_window_mixes_aware_and_naive_without_raising():
    # start aware, end absent -> end falls back to the naive _NOW default.
    # Comparing them in _resolve_window's `start > end` must not TypeError.
    app = create_app()
    app.testing = True
    with app.test_request_context("/?start=2026-05-01T00:00:00%2B09:00"):
        start, end = _resolve_window()
    assert start.tzinfo is None
    assert end.tzinfo is None
    assert start <= end


def test_resolve_window_returns_naive_for_z_suffixed_pair():
    app = create_app()
    app.testing = True
    with app.test_request_context(
        "/?start=2026-08-19T20:38:00Z&end=2026-08-19T21:38:00Z"
    ):
        start, end = _resolve_window()
    assert (start, end) == (datetime(2026, 8, 20, 5, 38), datetime(2026, 8, 20, 6, 38))
