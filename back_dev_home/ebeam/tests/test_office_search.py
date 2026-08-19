"""Focused tests for the shared Hitachi OpenSearch aggregation boundary."""

from typing import Any

import pytest
from opensearchpy.exceptions import NotFoundError

from back_dev_home._logging import os_timing
from back_dev_home.ebeam import _office_search


INDEX = "meas_hist_cdsem"


def _clean_response() -> dict[str, Any]:
    return {
        "took": 4,
        "timed_out": False,
        "_shards": {
            "total": 2,
            "successful": 2,
            "skipped": 0,
            "failed": 0,
        },
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "max_score": None,
            "hits": [],
        },
        "aggregations": {
            "comp": {
                "buckets": [],
            },
        },
    }


class _FakeSearch:
    def __init__(
        self,
        response: Any = None,
        error: Exception | None = None,
    ) -> None:
        self._response = response
        self._error = error

    def aggregate(
        self,
        _aggs: dict[str, Any],
        *,
        query: dict[str, Any] | None,
    ) -> Any:
        if self._error is not None:
            raise self._error
        return self._response

    def search_raw(self, _body: dict[str, Any]) -> Any:
        if self._error is not None:
            raise self._error
        return self._response


def _stub_response(monkeypatch, response: Any) -> None:
    monkeypatch.setattr(
        _office_search,
        "search",
        lambda _index: _FakeSearch(response=response),
    )


def test_aggregate_returns_aggregations_from_a_clean_response(monkeypatch):
    response = _clean_response()
    _stub_response(monkeypatch, response)

    result = _office_search.aggregate(
        INDEX,
        {"comp": {"composite": {"sources": []}}},
        {"bool": {"filter": []}},
    )

    assert result == response["aggregations"]


def test_aggregate_rejects_a_timed_out_response(monkeypatch):
    response = _clean_response()
    response["timed_out"] = True
    _stub_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match=r"meas_hist_cdsem.*timed_out.*false"):
        _office_search.aggregate(INDEX, {}, None)


def test_aggregate_rejects_failed_shards(monkeypatch):
    response = _clean_response()
    response["_shards"]["failed"] = 1
    _stub_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match=r"meas_hist_cdsem.*failed.*1"):
        _office_search.aggregate(INDEX, {}, None)


@pytest.mark.parametrize(
    "timed_out",
    [
        pytest.param(None, id="null"),
        pytest.param(0, id="integer-zero"),
        pytest.param("false", id="string-false"),
    ],
)
def test_aggregate_rejects_missing_or_malformed_timed_out(
    monkeypatch,
    timed_out,
):
    response = _clean_response()
    if timed_out is None:
        response.pop("timed_out")
    else:
        response["timed_out"] = timed_out
    _stub_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match=r"meas_hist_cdsem.*timed_out.*false"):
        _office_search.aggregate(INDEX, {}, None)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        pytest.param(
            lambda response: response.pop("_shards"),
            r"_shards.*mapping",
            id="missing-shards",
        ),
        pytest.param(
            lambda response: response.update({"_shards": []}),
            r"_shards.*mapping",
            id="non-mapping-shards",
        ),
        pytest.param(
            lambda response: response["_shards"].pop("failed"),
            r"_shards\.failed.*integer",
            id="missing-failed",
        ),
        pytest.param(
            lambda response: response["_shards"].update({"failed": True}),
            r"_shards\.failed.*integer",
            id="boolean-true-failed",
        ),
        pytest.param(
            lambda response: response["_shards"].update({"failed": False}),
            r"_shards\.failed.*integer",
            id="boolean-false-failed",
        ),
        pytest.param(
            lambda response: response["_shards"].update({"failed": 0.0}),
            r"_shards\.failed.*integer",
            id="float-failed",
        ),
        pytest.param(
            lambda response: response["_shards"].update({"failed": -1}),
            r"_shards\.failed.*non-negative",
            id="negative-failed",
        ),
    ],
)
def test_aggregate_rejects_missing_or_malformed_shard_status(
    monkeypatch,
    mutate,
    reason,
):
    response = _clean_response()
    mutate(response)
    _stub_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match=rf"meas_hist_cdsem.*{reason}"):
        _office_search.aggregate(INDEX, {}, None)


@pytest.mark.parametrize(
    "aggregations",
    [
        pytest.param(None, id="missing"),
        pytest.param([], id="list"),
        pytest.param("invalid", id="string"),
    ],
)
def test_aggregate_rejects_missing_or_malformed_aggregations(
    monkeypatch,
    aggregations,
):
    response = _clean_response()
    if aggregations is None:
        response.pop("aggregations")
    else:
        response["aggregations"] = aggregations
    _stub_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match=r"meas_hist_cdsem.*aggregations.*mapping"):
        _office_search.aggregate(INDEX, {}, None)


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(None, id="null"),
        pytest.param([], id="list"),
    ],
)
def test_aggregate_rejects_a_non_mapping_response(monkeypatch, response):
    _stub_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match=r"meas_hist_cdsem.*mapping"):
        _office_search.aggregate(INDEX, {}, None)


def test_aggregate_translates_not_found_error_to_lookup_error(monkeypatch):
    error = NotFoundError(404, "missing", {"error": "index_not_found_exception"})
    monkeypatch.setattr(
        _office_search,
        "search",
        lambda _index: _FakeSearch(error=error),
    )

    with pytest.raises(
        LookupError,
        match=r"meas_hist_cdsem.*not found",
    ) as raised:
        _office_search.aggregate(INDEX, {}, None)

    assert raised.value.__cause__ is error


# ── round-trip accounting ────────────────────────────────────────────────────
#
# These two helpers are where every office adapter's OpenSearch traffic passes,
# so counting here counts everything without an adapter having to opt in.


def test_aggregate_counts_one_round_trip_against_the_request(monkeypatch):
    _stub_response(monkeypatch, _clean_response())

    with os_timing.collect():
        _office_search.aggregate(INDEX, {}, None)
        summary = os_timing.summary()

    assert summary.query_count == 1
    assert summary.slowest_index == INDEX


def test_fetch_hits_counts_one_round_trip_against_the_request(monkeypatch):
    _stub_response(monkeypatch, _clean_response())

    with os_timing.collect():
        _office_search.fetch_hits(INDEX, None, 10)
        summary = os_timing.summary()

    assert summary.query_count == 1
    assert summary.slowest_index == INDEX


def test_a_failed_query_still_spent_a_round_trip(monkeypatch):
    # A missing alias costs the same HTTP round trip a successful one does. A
    # screen whose fan-out only shows up when something is broken is exactly
    # the screen worth knowing about.
    monkeypatch.setattr(
        _office_search,
        "search",
        lambda _index: _FakeSearch(
            error=NotFoundError(404, "missing", {"error": "index_not_found_exception"})
        ),
    )

    with os_timing.collect():
        with pytest.raises(LookupError):
            _office_search.aggregate(INDEX, {}, None)
        summary = os_timing.summary()

    assert summary.query_count == 1


def test_queries_outside_a_request_are_not_counted_and_do_not_fail(monkeypatch):
    # bm_pm's `_diagnose` and the scheduler jobs call these helpers with no
    # request in flight.
    _stub_response(monkeypatch, _clean_response())

    _office_search.aggregate(INDEX, {}, None)

    assert os_timing.summary() is None
