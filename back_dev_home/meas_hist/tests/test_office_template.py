"""Home-safe unit tests for the tracked OpenSearch adapter template."""

from datetime import datetime, timezone

import pytest

from back_dev_home.ebeam.hitachi import _office_meas_hist, _office_search
from back_dev_home.meas_hist.providers import office_example


class _FakeSearch:
    def __init__(self, captured):
        self._captured = captured

    def search_raw(self, body):
        self._captured["raw_body"] = body
        return {"hits": {"total": {"value": 0}, "hits": []}}


class _PartialAggregateSearch:
    def aggregate(self, _aggs, *, query):
        return {
            "timed_out": False,
            "_shards": {
                "total": 2,
                "successful": 1,
                "skipped": 0,
                "failed": 1,
            },
            "aggregations": {
                "comp": {
                    "buckets": [
                        {"key": {"group": "UNSAFE/PARTIAL_RECIPE"}},
                    ],
                },
            },
        }


def _stable_window(monkeypatch):
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        office_example,
        "_resolve_window",
        lambda *_args: (start, end, False, end),
    )
    monkeypatch.setattr(
        office_example,
        "_retention_window",
        lambda: (start, end),
    )


def test_recipe_name_composite_reuses_raw_query_and_extracts_sorted_names(monkeypatch):
    captured = {}
    _stable_window(monkeypatch)
    monkeypatch.setattr(
        office_example,
        "_os_search",
        lambda index: captured.setdefault("raw_index", index) and _FakeSearch(captured),
    )

    def fake_composite(index, field, sub_aggs, query):
        captured["composite"] = {
            "index": index,
            "field": field,
            "sub_aggs": sub_aggs,
            "query": query,
        }
        return [
            {"key": {"group": "Z/Z_RECIPE"}},
            {"key": {"group": "A/A_RECIPE"}},
            {"key": {"group": "A/A_RECIPE"}},
        ]

    monkeypatch.setattr(
        office_example,
        "_composite_buckets",
        fake_composite,
        raising=False,
    )

    result = office_example.search_meas_hist(
        tool_type="cd-sem",
        fab=["r3"],
        eq=["ecxdx001"],
        recipe=["CD_BIAS", "GATE_PITCH"],
        q=["ABC"],
        limit=1,
    )

    assert result["recipe_names"] == ["A/A_RECIPE", "Z/Z_RECIPE"]
    assert result["recipe_names_complete"] is True
    assert captured["composite"] == {
        "index": "meas_hist_cdsem",
        "field": "full_name.keyword",
        "sub_aggs": {},
        "query": captured["raw_body"]["query"],
    }


@pytest.mark.parametrize("group", ["", "   ", 7, False])
def test_invalid_full_name_bucket_group_propagates_instead_of_marking_complete(
    monkeypatch,
    group,
):
    captured = {}
    _stable_window(monkeypatch)
    monkeypatch.setattr(
        office_example,
        "_os_search",
        lambda index: captured.setdefault("raw_index", index) and _FakeSearch(captured),
    )
    monkeypatch.setattr(
        office_example,
        "_composite_buckets",
        lambda *_args: [{"key": {"group": group}}],
    )

    with pytest.raises(
        RuntimeError,
        match=r"full_name.*bucket 1.*nonblank string",
    ):
        office_example.search_meas_hist(
            tool_type="cd-sem",
            recipe=["CD_BIAS"],
            limit=1,
        )


def test_malformed_recipe_aggregation_propagates_instead_of_marking_complete(
    monkeypatch,
):
    captured = {}
    _stable_window(monkeypatch)
    monkeypatch.setattr(
        office_example,
        "_os_search",
        lambda index: captured.setdefault("raw_index", index) and _FakeSearch(captured),
    )
    monkeypatch.setattr(
        _office_meas_hist,
        "aggregate",
        lambda *_args: {"comp": {}},
    )

    with pytest.raises(RuntimeError, match="missing.*buckets"):
        office_example.search_meas_hist(
            tool_type="cd-sem",
            recipe=["CD_BIAS"],
            limit=1,
        )


def test_malformed_mapping_after_key_propagates_instead_of_marking_complete(
    monkeypatch,
):
    captured = {}
    _stable_window(monkeypatch)
    monkeypatch.setattr(
        office_example,
        "_os_search",
        lambda index: captured.setdefault("raw_index", index) and _FakeSearch(captured),
    )
    monkeypatch.setattr(
        _office_meas_hist,
        "aggregate",
        lambda *_args: {
            "comp": {
                "buckets": [],
                "after_key": {},
            },
        },
    )

    with pytest.raises(RuntimeError, match="after_key.*exactly.*group"):
        office_example.search_meas_hist(
            tool_type="cd-sem",
            recipe=["CD_BIAS"],
            limit=1,
        )


def test_partial_raw_aggregation_propagates_through_shared_validation(
    monkeypatch,
):
    captured = {}
    _stable_window(monkeypatch)
    monkeypatch.setattr(
        office_example,
        "_os_search",
        lambda index: captured.setdefault("raw_index", index) and _FakeSearch(captured),
    )
    monkeypatch.setattr(
        _office_search,
        "search",
        lambda _index: _PartialAggregateSearch(),
    )

    with pytest.raises(RuntimeError, match=r"meas_hist_cdsem.*failed.*1"):
        office_example.search_meas_hist(
            tool_type="cd-sem",
            recipe=["CD_BIAS"],
            limit=1,
        )


def test_recipe_name_composite_is_not_called_without_recipe_filter(monkeypatch):
    captured = {}
    _stable_window(monkeypatch)
    monkeypatch.setattr(
        office_example,
        "_os_search",
        lambda index: captured.setdefault("raw_index", index) and _FakeSearch(captured),
    )

    def unexpected_composite(*_args, **_kwargs):
        raise AssertionError("recipe aggregation must not run without recipe filters")

    monkeypatch.setattr(
        office_example,
        "_composite_buckets",
        unexpected_composite,
        raising=False,
    )

    result = office_example.search_meas_hist(limit=1)

    assert result["recipe_names"] == []
    assert result["recipe_names_complete"] is False


@pytest.mark.parametrize(
    "date_params",
    [
        {"date_from": "not-a-date"},
        {"date_to": "2020-01-01"},
        {"date_from": "2099-01-01"},
    ],
)
def test_recipe_names_are_incomplete_when_date_range_is_rejected(
    monkeypatch,
    date_params,
):
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(office_example, "_retention_window", lambda: (start, end))

    def unexpected_search(*_args, **_kwargs):
        raise AssertionError("raw search must not run outside retention")

    def unexpected_composite(*_args, **_kwargs):
        raise AssertionError("recipe aggregation must not run outside retention")

    monkeypatch.setattr(office_example, "_os_search", unexpected_search)
    monkeypatch.setattr(
        office_example,
        "_composite_buckets",
        unexpected_composite,
    )

    result = office_example.search_meas_hist(
        recipe=["CD_BIAS"],
        **date_params,
    )

    assert result["out_of_retention"] is True
    assert result["recipe_names"] == []
    assert result["recipe_names_complete"] is False
