"""Focused tests for shared meas_hist OpenSearch pagination helpers."""

import pytest

from back_dev_home.ebeam.hitachi import _office_meas_hist


def _stub_composite_pages(monkeypatch, pages, *, page_size=2):
    responses = iter(pages)
    calls = []

    def fake_aggregate(index, body, query_body):
        calls.append((index, body, query_body))
        return next(responses)

    monkeypatch.setattr(_office_meas_hist, "aggregate", fake_aggregate)
    monkeypatch.setattr(
        _office_meas_hist,
        "_COMPOSITE_PAGE_SIZE",
        page_size,
    )
    return calls


def test_composite_buckets_accepts_a_valid_empty_page(monkeypatch):
    calls = _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": []}}],
    )

    assert _office_meas_hist.composite_buckets(
        "meas_hist_cdsem",
        "full_name.keyword",
        {},
        {"bool": {"filter": []}},
    ) == []
    assert len(calls) == 1


def test_composite_buckets_walks_valid_multiple_pages(monkeypatch):
    first_page = [
        {"key": {"group": "A"}},
        {"key": {"group": "B"}},
    ]
    last_page = [{"key": {"group": "C"}}]
    calls = _stub_composite_pages(
        monkeypatch,
        [
            {
                "comp": {
                    "buckets": first_page,
                    "after_key": {"group": "B"},
                },
            },
            {"comp": {"buckets": last_page}},
        ],
    )

    assert _office_meas_hist.composite_buckets(
        "meas_hist_cdsem",
        "full_name.keyword",
        {"total": {"sum": {"field": "meastime"}}},
        {"bool": {"filter": []}},
    ) == [*first_page, *last_page]
    assert len(calls) == 2
    assert "after" not in calls[0][1]["comp"]["composite"]
    assert calls[1][1]["comp"]["composite"]["after"] == {"group": "B"}


def test_composite_buckets_preserves_valid_scalar_buckets_and_sub_aggs(monkeypatch):
    page_buckets = [
        {
            "key": {"group": "A"},
            "doc_count": 3,
            "total": {"value": 12.5},
        },
        {
            "key": {"group": 7},
            "doc_count": 2,
            "sample": {"hits": {"hits": [{"_source": {"name": "seven"}}]}},
        },
        {
            "key": {"group": 1.5},
            "doc_count": 1,
            "latest": {"value_as_string": "2026-07-27T00:00:00"},
        },
        {
            "key": {"group": False},
            "doc_count": 4,
            "metric": {"value": 0},
        },
    ]
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": page_buckets}}],
    )

    assert _office_meas_hist.composite_buckets(
        "meas_hist_cdsem",
        "full_name.keyword",
        {"total": {"sum": {"field": "meastime"}}},
        None,
    ) == page_buckets


@pytest.mark.parametrize("bucket", [None, [], "bucket"])
def test_composite_buckets_rejects_non_mapping_bucket(monkeypatch, bucket):
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [{"key": {"group": "A"}}, bucket]}}],
    )

    with pytest.raises(
        RuntimeError,
        match=r"bucket 2.*page 1.*meas_hist_cdsem.*mapping",
    ):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )


@pytest.mark.parametrize("bucket", [{}, {"key": None}, {"key": []}])
def test_composite_buckets_rejects_missing_or_non_mapping_bucket_key(
    monkeypatch,
    bucket,
):
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [{"key": {"group": "A"}}, bucket]}}],
    )

    with pytest.raises(
        RuntimeError,
        match=r"bucket 2.*page 1.*meas_hist_cdsem.*key.*mapping",
    ):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )


@pytest.mark.parametrize(
    "key",
    [
        {},
        {"other": "A"},
        {"group": "A", "other": "B"},
    ],
)
def test_composite_buckets_rejects_bucket_key_with_wrong_schema(monkeypatch, key):
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [{"key": {"group": "A"}}, {"key": key}]}}],
    )

    with pytest.raises(
        RuntimeError,
        match=r"bucket 2.*page 1.*meas_hist_cdsem.*key.*exactly.*group",
    ):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )


@pytest.mark.parametrize("group", [None, {}, []])
def test_composite_buckets_rejects_null_or_collection_bucket_group(
    monkeypatch,
    group,
):
    _stub_composite_pages(
        monkeypatch,
        [
            {
                "comp": {
                    "buckets": [
                        {"key": {"group": "A"}},
                        {"key": {"group": group}},
                    ]
                }
            }
        ],
    )

    with pytest.raises(
        RuntimeError,
        match=r"bucket 2.*page 1.*meas_hist_cdsem.*key\.group.*JSON scalar",
    ):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ({}, "missing.*comp"),
        ({"comp": []}, "comp.*mapping"),
        ({"comp": {}}, "missing.*buckets"),
        ({"comp": {"buckets": {}}}, "buckets.*list"),
    ],
)
def test_composite_buckets_rejects_malformed_aggregation_envelopes(
    monkeypatch,
    response,
    message,
):
    _stub_composite_pages(monkeypatch, [response])

    with pytest.raises(RuntimeError, match=message):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )


@pytest.mark.parametrize("after_key", [None, [], "next"])
def test_composite_buckets_rejects_malformed_after_key(
    monkeypatch,
    after_key,
):
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [], "after_key": after_key}}],
    )

    with pytest.raises(RuntimeError, match="after_key.*mapping"):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )


@pytest.mark.parametrize(
    "after_key",
    [
        {},
        {"cursor": "A"},
        {"group": "A", "cursor": "B"},
    ],
)
def test_composite_buckets_rejects_after_key_with_wrong_schema(
    monkeypatch,
    after_key,
):
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [], "after_key": after_key}}],
    )

    with pytest.raises(
        RuntimeError,
        match=r"page 1.*meas_hist_cdsem.*after_key.*exactly.*group",
    ):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )


@pytest.mark.parametrize(
    "group",
    [
        None,
        {},
        [],
        (),
        set(),
    ],
)
def test_composite_buckets_rejects_non_scalar_after_key_group(
    monkeypatch,
    group,
):
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [], "after_key": {"group": group}}}],
    )

    with pytest.raises(
        RuntimeError,
        match=r"page 1.*meas_hist_cdsem.*after_key\.group.*JSON scalar",
    ):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )


@pytest.mark.parametrize(
    "group",
    [
        "B",
        "",
        0,
        -7,
        1.5,
        True,
        False,
    ],
)
def test_composite_buckets_preserves_valid_scalar_after_key_group(
    monkeypatch,
    group,
):
    calls = _stub_composite_pages(
        monkeypatch,
        [
            {
                "comp": {
                    "buckets": [{"key": {"group": group}}],
                    "after_key": {"group": group},
                },
            },
            {"comp": {"buckets": []}},
        ],
        page_size=1,
    )

    assert _office_meas_hist.composite_buckets(
        "meas_hist_cdsem",
        "full_name.keyword",
        {},
        None,
    ) == [{"key": {"group": group}}]
    sent_group = calls[1][1]["comp"]["composite"]["after"]["group"]
    assert sent_group == group
    assert type(sent_group) is type(group)


def test_composite_buckets_rejects_a_repeated_after_key(monkeypatch):
    _stub_composite_pages(
        monkeypatch,
        [
            {
                "comp": {
                    "buckets": [{"key": {"group": "A"}}],
                    "after_key": {"group": "A"},
                },
            },
            {
                "comp": {
                    "buckets": [{"key": {"group": "B"}}],
                    "after_key": {"group": "A"},
                },
            },
        ],
        page_size=1,
    )

    with pytest.raises(RuntimeError, match="repeated.*after_key"):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            "full_name.keyword",
            {},
            None,
        )
