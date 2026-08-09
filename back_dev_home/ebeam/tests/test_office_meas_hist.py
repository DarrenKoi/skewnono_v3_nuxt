"""Focused tests for shared meas_hist OpenSearch pagination helpers.

`_composite_sources` 는 OpenSearch 없이 순수 함수로 검사합니다. 기존
`field: str` 호출을 깨면 사무실의 아직 갱신되지 않은 office.py 사본들이
import 에러로 앱 팩토리 전체를 죽입니다 — 그래서 하위호환이 테스트로
고정되어야 합니다.
"""

import pytest

from back_dev_home.ebeam import _office_meas_hist
from back_dev_home.ebeam._office_meas_hist import _composite_sources


def test_single_field_keeps_the_legacy_group_source():
    assert _composite_sources("full_name.keyword") == [
        {"group": {"terms": {"field": "full_name.keyword"}}}
    ]


def test_multiple_sources_preserve_order_and_names():
    assert _composite_sources([
        ("eqp", "eqp_id.keyword"),
        ("fab", "fab_name.keyword"),
    ]) == [
        {"eqp": {"terms": {"field": "eqp_id.keyword"}}},
        {"fab": {"terms": {"field": "fab_name.keyword"}}},
    ]


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


def test_legacy_error_wording_is_byte_identical(monkeypatch):
    """소스가 하나일 때의 문구는 글자 그대로 보존됩니다.

    위 검사들의 정규식(`.*key.*exactly.*group`)은 "exactly one key **called**
    'group'" 같은 재작문을 통과시킵니다. 사무실 운영자가 한 번 본 문구를
    로그에서 grep 하거나 문서에 붙여 둘 수 있으므로 == 로 못 박습니다.
    """
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [{"key": {"other": "A"}}]}}],
    )
    with pytest.raises(RuntimeError) as excinfo:
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem", "full_name.keyword", {}, None
        )
    assert str(excinfo.value) == (
        "OpenSearch composite bucket 1 on page 1 for 'meas_hist_cdsem' "
        "'key' must contain exactly one key named 'group'; got keys ['other']."
    )

    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [{"key": {"group": None}}]}}],
    )
    with pytest.raises(RuntimeError) as excinfo:
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem", "full_name.keyword", {}, None
        )
    assert str(excinfo.value) == (
        "OpenSearch composite bucket 1 on page 1 for 'meas_hist_cdsem' "
        "'key.group' must be a non-null JSON scalar "
        "(string, number, or boolean); got NoneType."
    )

    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [], "after_key": {"cursor": "A"}}}],
    )
    with pytest.raises(RuntimeError) as excinfo:
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem", "full_name.keyword", {}, None
        )
    assert str(excinfo.value) == (
        "OpenSearch composite page 1 for 'meas_hist_cdsem' "
        "'after_key' must contain exactly one key named 'group'; "
        "got keys ['cursor']."
    )


def test_composite_buckets_accepts_multi_source_bucket_keys(monkeypatch):
    # 다중 소스로 부르면 버킷 키는 소스 이름마다 하나씩입니다. 검증기가
    # 'group' 하나만 허용하면 /equipments 의 4-소스 집계가 첫 버킷에서
    # 죽습니다.
    page_buckets = [
        {"key": {"eqp": "CD01", "recipe": "ADI/A"}, "doc_count": 3, "tat": {"value": 30}},
        {"key": {"eqp": "CD02", "recipe": "ADI/B"}, "doc_count": 1, "tat": {"value": 9}},
    ]
    _stub_composite_pages(monkeypatch, [{"comp": {"buckets": page_buckets}}])

    assert _office_meas_hist.composite_buckets(
        "meas_hist_cdsem",
        [("eqp", "eqp_id.keyword"), ("recipe", "full_name.keyword")],
        {"tat": {"sum": {"field": "meastime"}}},
        None,
    ) == page_buckets


def test_composite_buckets_paginates_with_a_multi_source_after_key(monkeypatch):
    after_key = {"eqp": "CD01", "recipe": "ADI/A"}
    calls = _stub_composite_pages(
        monkeypatch,
        [
            {"comp": {"buckets": [{"key": after_key}], "after_key": after_key}},
            {"comp": {"buckets": []}},
        ],
        page_size=1,
    )

    assert _office_meas_hist.composite_buckets(
        "meas_hist_cdsem",
        [("eqp", "eqp_id.keyword"), ("recipe", "full_name.keyword")],
        {},
        None,
    ) == [{"key": after_key}]
    assert calls[0][1]["comp"]["composite"]["sources"] == [
        {"eqp": {"terms": {"field": "eqp_id.keyword"}}},
        {"recipe": {"terms": {"field": "full_name.keyword"}}},
    ]
    assert calls[1][1]["comp"]["composite"]["after"] == after_key


@pytest.mark.parametrize(
    "key",
    [
        {"eqp": "CD01"},                            # 소스 하나가 빠짐
        {"eqp": "CD01", "group": "ADI/A"},          # 옛 이름이 섞임
        {"eqp": "CD01", "recipe": "ADI/A", "x": 1},  # 모르는 키가 더 있음
    ],
)
def test_composite_buckets_rejects_multi_source_key_with_wrong_schema(monkeypatch, key):
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [{"key": key}]}}],
    )

    with pytest.raises(
        RuntimeError,
        match=r"bucket 1.*page 1.*meas_hist_cdsem.*key.*exactly.*eqp.*recipe",
    ):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            [("eqp", "eqp_id.keyword"), ("recipe", "full_name.keyword")],
            {},
            None,
        )


def test_composite_buckets_rejects_a_non_scalar_multi_source_key_value(monkeypatch):
    _stub_composite_pages(
        monkeypatch,
        [{"comp": {"buckets": [{"key": {"eqp": "CD01", "recipe": None}}]}}],
    )

    with pytest.raises(
        RuntimeError,
        match=r"bucket 1.*page 1.*meas_hist_cdsem.*key\.recipe.*JSON scalar",
    ):
        _office_meas_hist.composite_buckets(
            "meas_hist_cdsem",
            [("eqp", "eqp_id.keyword"), ("recipe", "full_name.keyword")],
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
