"""Per-request OpenSearch round-trip accounting.

The question this accounting exists to answer is not "how long was that
query" but "how many round trips does one screen make, and is the time in the
count or in one slow query" — the three-way split that decides whether
batching (msearch) could ever help. So the tests below assert on the summary's
shape, not on wall-clock numbers.
"""

import pytest

from back_dev_home._logging import os_timing


@pytest.fixture(autouse=True)
def _no_leaked_collector():
    """Each test starts with no collector installed, as a fresh thread would."""
    assert os_timing.summary() is None
    yield
    assert os_timing.summary() is None


def test_recording_without_a_collector_is_a_silent_no_op():
    # Standalone diagnostics and scheduler jobs call the same query helpers
    # outside any request. They must not need to know this module exists.
    os_timing.record("cdsem_idp_ver", 12.0)
    assert os_timing.summary() is None


def test_a_request_with_no_queries_reports_nothing():
    with os_timing.collect():
        summary = os_timing.summary()
    # Not a zero-filled summary: `_record_to_doc` omits None, so a request that
    # never touched OpenSearch leaves no os fields in the log document at all.
    assert summary is None


def test_counts_round_trips_and_totals_their_time():
    with os_timing.collect():
        os_timing.record("cdsem_idp_ver", 10.4)
        os_timing.record("cdsem_idp_ver", 4.6)
        os_timing.record("meas_hist_cdsem", 5.0)
        summary = os_timing.summary()

    assert summary.query_count == 3
    assert summary.total_ms == 20


def test_the_slowest_query_is_named_so_one_trip_finds_it():
    with os_timing.collect():
        os_timing.record("cdsem_idp_ver", 8.0)
        os_timing.record("meas_hist_cdsem", 91.0)
        os_timing.record("cdsem_idp_ver", 3.0)
        summary = os_timing.summary()

    # slowest_ms against total_ms is the discriminator: one dominant query
    # means batching cannot help, many small ones means it might.
    assert summary.slowest_ms == 91
    assert summary.slowest_index == "meas_hist_cdsem"


def test_a_collector_does_not_outlive_its_request():
    # uWSGI reuses request threads. A collector left installed would attribute
    # the next request's queries to a request that already answered.
    with os_timing.collect():
        os_timing.record("cdsem_idp_ver", 1.0)
    assert os_timing.summary() is None


def test_nested_collection_restores_the_outer_request():
    with os_timing.collect():
        os_timing.record("outer_index", 5.0)
        with os_timing.collect():
            os_timing.record("inner_index", 50.0)
            assert os_timing.summary().query_count == 1
        summary = os_timing.summary()

    assert summary.query_count == 1
    assert summary.slowest_index == "outer_index"


def test_the_summary_fields_are_ints_the_index_maps_as_integer():
    with os_timing.collect():
        os_timing.record("cdsem_idp_ver", 0.4)
        summary = os_timing.summary()

    # LOG_MAPPING_PROPERTIES types these as `integer`; a float here indexes as
    # a truncated value at the office and as a float in every home assertion,
    # which is the drift that only shows up in production aggregations.
    assert isinstance(summary.total_ms, int)
    assert isinstance(summary.slowest_ms, int)
    assert isinstance(summary.query_count, int)


def test_a_sub_millisecond_query_still_counts_as_a_round_trip():
    # Rounding time to 0 must not round the round trip away — the count is the
    # decision variable, and a warm cached query is still an HTTP round trip.
    with os_timing.collect():
        os_timing.record("cdsem_idp_ver", 0.2)
        summary = os_timing.summary()

    assert summary.query_count == 1
    assert summary.total_ms == 0


def test_as_extra_gives_the_keys_the_log_document_maps():
    with os_timing.collect():
        os_timing.record("cdsem_idp_ver", 7.0)
        extra = os_timing.summary().as_extra()

    assert extra == {
        "opensearch_query_count": 1,
        "opensearch_total_ms": 7,
        "opensearch_slowest_ms": 7,
        "opensearch_slowest_index": "cdsem_idp_ver",
    }
