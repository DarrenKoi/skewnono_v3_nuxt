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
