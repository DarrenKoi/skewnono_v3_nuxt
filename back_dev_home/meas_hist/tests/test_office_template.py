"""Home-safe unit tests for the tracked OpenSearch adapter template."""

from datetime import datetime, timezone

import pytest

from back_dev_home.ebeam import _office_meas_hist, _office_search
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


def test_recipe_name_composite_reuses_raw_query_and_extracts_sorted_pairs(monkeypatch):
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
        # Two buckets for the same full_name with different fab sub-buckets
        # must accumulate into distinct (name, fab) pairs, not collapse.
        return [
            {
                "key": {"group": "Z/Z_RECIPE"},
                "fabs": {"buckets": [{"key": "R3", "doc_count": 4}]},
            },
            {
                "key": {"group": "A/A_RECIPE"},
                "fabs": {"buckets": [{"key": "M16B", "doc_count": 2}]},
            },
            {
                "key": {"group": "A/A_RECIPE"},
                "fabs": {"buckets": [{"key": "R3", "doc_count": 1}]},
            },
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

    assert result["recipe_names"] == [
        {"full_name": "A/A_RECIPE", "fab_name": "M16B"},
        {"full_name": "A/A_RECIPE", "fab_name": "R3"},
        {"full_name": "Z/Z_RECIPE", "fab_name": "R3"},
    ]
    assert result["recipe_names_complete"] is True
    assert captured["composite"] == {
        "index": "meas_hist_cdsem",
        "field": "full_name.keyword",
        "sub_aggs": {"fabs": {"terms": {"field": "fab_name.keyword", "size": 16}}},
        "query": captured["raw_body"]["query"],
    }


def test_recipe_name_composite_keeps_names_with_no_fab_buckets(monkeypatch):
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
        lambda *_args, **_kwargs: [
            {"key": {"group": "A/NO_FAB_RECIPE"}, "fabs": {"buckets": []}},
        ],
        raising=False,
    )

    result = office_example.search_meas_hist(recipe=["NO_FAB"], limit=1)

    # Dirty office docs without fab_name must not hide the recipe — the pair
    # survives with an empty fab ("owner unknown" per the contract).
    assert result["recipe_names"] == [
        {"full_name": "A/NO_FAB_RECIPE", "fab_name": ""},
    ]
    assert result["recipe_names_complete"] is True


def test_recipe_name_composite_rejects_missing_fabs_sub_aggregation(monkeypatch):
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
        lambda *_args, **_kwargs: [{"key": {"group": "A/A_RECIPE"}}],
        raising=False,
    )

    with pytest.raises(RuntimeError, match=r"fabs.*sub-aggregation"):
        office_example.search_meas_hist(recipe=["CD_BIAS"], limit=1)


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


# ── the msr identity: field where present, _id otherwise ────────────────────
# Regression 2026-08-20: 21,474 of 2,250,652 office documents carry no `msr`
# field, and the NEWEST ones are among them -- the segment a default 스큐보아
# search returns. Reading only _source["msr"] gave those rows an empty
# identity, so every one of them lost its click while minio_msr/minio_pkl sat
# populated in the same document. The _id IS the msr (user-confirmed).

_ID_ONLY_HIT = {
    "_id": "20260819_ADI_CD_BIAS_001_RAEA240031_ECXDX123",
    "_index": "meas_hist_cdsem",
    "_source": {
        "lot_id": "RAEA240031",
        "eqp_id": "ECXDX123",
        "eqp_model_cd": "CG6300",
        "msr_check": "Yes",
        "minio_pkl": "hitachi_sem/cdsem/dict_pkl/2026/x.pkl",
        "timestamp": "2026-08-19T10:00:00",
    },
}


def test_row_takes_the_msr_from_the_id_when_the_field_is_absent():
    row = office_example._row(_ID_ONLY_HIT, "cd-sem", {})

    assert row["msr"] == _ID_ONLY_HIT["_id"]
    # id = msr is the datatable rule; it must hold on this path too.
    assert row["id"] == _ID_ONLY_HIT["_id"]


def test_row_prefers_the_stored_field_when_the_document_has_one():
    hit = {**_ID_ONLY_HIT, "_source": {**_ID_ONLY_HIT["_source"], "msr": "FROM-FIELD"}}

    assert office_example._row(hit, "cd-sem", {})["msr"] == "FROM-FIELD"


def test_msr_lookup_matches_documents_whose_id_carries_the_identity(monkeypatch):
    captured = {}

    class _Search:
        def search_raw(self, body):
            captured["body"] = body
            return {"hits": {"hits": [_ID_ONLY_HIT]}}

    monkeypatch.setattr(office_example, "_os_search", lambda _index: _Search())

    row = office_example.find_meas_hist_by_msr(_ID_ONLY_HIT["_id"])

    assert row is not None and row["msr"] == _ID_ONLY_HIT["_id"]
    # An `ids` clause is the half that reaches a field-less document; a query
    # built only on msr.keyword would have returned nothing for it.
    assert "ids" in str(captured["body"])


def test_msr_lookup_still_refuses_an_empty_identity(monkeypatch):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("an empty msr must not reach OpenSearch")

    monkeypatch.setattr(office_example, "_os_search", unexpected)

    assert office_example.find_meas_hist_by_msr("") is None


def test_msr_filter_and_q_both_reach_id_only_documents(monkeypatch):
    captured = {}
    _stable_window(monkeypatch)
    monkeypatch.setattr(office_example, "_os_search", lambda _i: _FakeSearch(captured))
    monkeypatch.setattr(
        office_example,
        "_composite_buckets",
        lambda *_a, **_k: [],
        raising=False,
    )

    office_example.search_meas_hist(
        msr=[_ID_ONLY_HIT["_id"]],
        q=[_ID_ONLY_HIT["_id"]],
        limit=1,
    )

    # Both the explicit msr= filter and the pasted-into-the-search-bar path
    # must carry an ids clause; _id cannot be wildcarded, only matched whole.
    assert str(captured["raw_body"]).count("ids") >= 2
