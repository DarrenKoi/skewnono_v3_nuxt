import pytest
from flask import Flask, g

import ops_store
from back_dev_home._auth.provider import SOURCE_LOCAL
from back_dev_home._core.opensearch import wildcard_clause
from back_dev_home.admin_logs import routes
from back_dev_home.admin_logs.providers import mock, office_example
from back_dev_home.admin_logs.query import (
    item_from_hit,
    parse_iso_utc,
    parse_log_query,
    utc_now,
)


def test_parse_log_query_keeps_existing_filter_contract():
    parsed = parse_log_query(
        {
            "level": "error,warning",
            "method": "get",
            "page": "2",
            "page_size": "500",
        }
    )
    assert parsed.page == 2
    assert parsed.page_size == 200
    assert parsed.filters["level"] == "ERROR,WARNING"
    assert {"terms": {"level": ["ERROR", "WARNING"]}} in (
        parsed.query["bool"]["filter"]
    )


def test_hit_normalization_keeps_legacy_path_fallback_and_raw_source():
    source = {
        "@timestamp": "2026-07-27T00:00:00Z",
        "request_path": "/api/legacy",
        "level": "INFO",
        "custom": {"kept": True},
    }
    item = item_from_hit(
        {
            "_id": "event-1",
            "_index": "skewnono_logging-000001",
            "_source": source,
        }
    )
    assert item["path"] == "/api/legacy"
    assert item["raw"] == source
    assert item["id"] == "event-1"


def test_office_queries_the_resolved_local_alias(monkeypatch):
    seen = {}

    class FakeSearch:
        def __init__(self, index):
            seen["index"] = index

        def search_raw(self, body):
            seen["body"] = body
            return {"hits": {"total": {"value": 0}, "hits": []}}

    monkeypatch.setenv("SKEWNONO_LOG_ENV", "local")
    monkeypatch.setattr(office_example, "OSSearch", FakeSearch, raising=False)

    result = office_example.query_logs({})

    assert seen["index"] == "skewnono_logging_local"
    assert seen["body"]["from"] == 0
    assert seen["body"]["size"] == 50
    assert seen["body"]["track_total_hits"] is True
    assert seen["body"]["sort"] == [{"@timestamp": {"order": "desc"}}]
    assert result["filters"]["deployment"] == "local"
    assert result["filters"]["index_alias"] == "skewnono_logging_local"
    assert result["page_count"] == 1


def test_mock_never_constructs_opensearch(monkeypatch):
    class NeverSearch:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("mock provider must not construct OpenSearch")

    monkeypatch.setenv("OPENSEARCH_PASSWORD", "present")
    monkeypatch.setattr(ops_store, "OSSearch", NeverSearch)

    result = mock.query_logs({})

    assert result["filters"]["demo_mode"] is True
    assert all(item["index"].endswith("-demo") for item in result["items"])


def test_route_returns_stable_503_without_backend_details(monkeypatch):
    def fail(_params):
        raise ConnectionError("secret-internal-host:9200")

    monkeypatch.setattr(routes, "query_logs", fail)
    app = Flask(__name__)

    @app.before_request
    def identity():
        # Both fields, as the real gate sets them: require_admin now asks
        # is_admin_request(), which fails closed when a caller has an id but no
        # source — an id alone could be a self-declared one.
        g.user_id = "local-dev"
        g.identity_source = SOURCE_LOCAL

    app.register_blueprint(routes.bp, url_prefix="/api")
    response = app.test_client().get("/api/admin/logs")

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "log_query_failed"
    assert body["error"]["message"] == "Could not query OpenSearch logs"
    assert "secret-internal-host" not in str(body)


def test_route_maps_malformed_time_range_to_400_invalid_log_query():
    app = Flask(__name__)

    @app.before_request
    def identity():
        g.user_id = "local-dev"
        g.identity_source = SOURCE_LOCAL

    app.register_blueprint(routes.bp, url_prefix="/api")
    response = app.test_client().get("/api/admin/logs?from=not-a-date")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_log_query"


def test_parse_log_query_rejects_pages_beyond_the_result_window():
    """OpenSearch rejects from+size past 10k with an opaque 400-class error the
    route would relabel as a 503 outage; refusing up front keeps it a 400."""
    with pytest.raises(ValueError, match="result window"):
        parse_log_query({"page": "51", "page_size": "200"})

    assert parse_log_query({"page": "50", "page_size": "200"}).page == 50


def test_free_text_matches_error_name_as_substring():
    """error_name is keyword-mapped, so match_phrase would need the exact full
    value; the free-text box promises substring semantics like path."""
    should = parse_log_query({"q": "timeout"}).query["bool"]["must"][0]["bool"]["should"]

    assert wildcard_clause("error_name", "timeout") in should
    assert {"match_phrase": {"error_name": "timeout"}} not in should


def test_free_text_treats_user_wildcards_as_literal_characters():
    """The mock free-text filter is a plain Python substring test, so a user
    typing `*` means an asterisk. Interpolated raw into a wildcard pattern it
    would become match-anything and the office would return rows home never
    does — a divergence no home test can see."""
    should = parse_log_query({"q": "GET *"}).query["bool"]["must"][0]["bool"]["should"]
    patterns = [
        clause["wildcard"][field]["value"]
        for clause in should
        if "wildcard" in clause
        for field in clause["wildcard"]
    ]

    assert patterns and all(p == "*GET \\**" for p in patterns)


def test_free_text_and_path_match_case_insensitively_like_the_mock():
    """providers/mock.py lowercases both sides for `q` and `path`. A bare
    wildcard clause is case-SENSITIVE, so without this flag the same query
    quietly returns fewer rows at the office than at home."""
    parsed = parse_log_query({"q": "timeout", "path": "/api/sem"})
    should = parsed.query["bool"]["must"][0]["bool"]["should"]
    path_clause = next(
        c for c in parsed.query["bool"]["filter"] if "wildcard" in c
    )

    assert path_clause["wildcard"]["path"]["case_insensitive"] is True
    for clause in should:
        if "wildcard" in clause:
            for field in clause["wildcard"]:
                assert clause["wildcard"][field]["case_insensitive"] is True


def test_activity_kind_and_fab_name_narrow_the_query():
    """fab_name goes through the writer's normalize_fab_name_list, so casing
    and comma-separated input match what was actually indexed."""
    parsed = parse_log_query({"activity_kind": "feature", "fab_name": "m16b, m14"})

    filters = parsed.query["bool"]["filter"]
    assert {"term": {"activity_kind": "feature"}} in filters
    assert {"terms": {"fab_name_list": ["M16B", "M14"]}} in filters
    assert parsed.filters["activity_kind"] == "feature"
    assert parsed.filters["fab_name"] == "M16B,M14"


def test_malformed_time_range_raises_value_error_in_both_providers():
    """A typo in from/to must become 400 invalid_log_query, not the office's
    503 outage message — and the mock must reject it too instead of silently
    ignoring the filter."""
    with pytest.raises(ValueError, match="from must be an ISO-8601"):
        parse_log_query({"from": "not-a-date"})
    with pytest.raises(ValueError, match="to must be an ISO-8601"):
        parse_log_query({"to": "2026-13-45"})
    with pytest.raises(ValueError, match="from must be an ISO-8601"):
        mock.query_logs({"from": "yesterday-ish"})


def test_valid_time_range_is_accepted_and_applied_by_the_mock():
    parsed = parse_log_query(
        {"from": "2026-07-30T00:00:00Z", "to": "2026-07-31T00:00:00Z"}
    )
    assert parsed.filters["from"] == "2026-07-30T00:00:00Z"
    assert parsed.filters["to"] == "2026-07-31T00:00:00Z"

    # Demo rows are relative to now; a window that old matches none of them.
    old_window = mock.query_logs(
        {"from": "2020-01-01T00:00:00Z", "to": "2020-01-02T00:00:00Z"}
    )
    assert old_window["total"] == 0
    assert old_window["items"] == []

    # The default window (last 24 h) keeps every demo row.
    assert mock.query_logs({})["total"] == len(mock._demo_source(utc_now()))


def test_mock_time_filter_tolerates_an_unusable_row_timestamp():
    """A row whose @timestamp is missing or malformed must be passed over by the
    time filter, not raise — a raise here would reach the route as a 503."""
    window = (
        parse_iso_utc("2026-07-30T00:00:00Z"),
        parse_iso_utc("2026-07-31T00:00:00Z"),
    )
    filters = {"from": "2026-07-30T00:00:00Z", "to": "2026-07-31T00:00:00Z"}

    for row in ({}, {"@timestamp": None}, {"@timestamp": "not-a-date"}):
        assert mock._matches_demo(dict(row), filters, window) is True


def test_mock_free_text_covers_the_office_field_set():
    """q semantics are shared: the mock substring-matches exactly the fields
    the office should-clauses search (query.FREE_TEXT_FIELDS)."""
    # exception.stack is only reachable through the nested field.
    by_stack = mock.query_logs({"q": "Traceback"})
    assert by_stack["total"] == 1
    assert by_stack["items"][0]["raw"]["exception"]["stack"].startswith(
        "Traceback"
    )

    # query_string is not in the office field set, so it must not match.
    assert mock.query_logs({"q": "top=10"})["total"] == 0


def test_mock_filters_by_activity_kind_and_fab_name():
    by_kind = mock.query_logs({"activity_kind": "feature"})
    assert by_kind["items"]
    assert all(
        item["raw"]["activity_kind"] == "feature" for item in by_kind["items"]
    )

    by_fab = mock.query_logs({"fab_name": "M16B"})
    assert by_fab["items"]
    assert all(
        "M16B" in item["raw"]["fab_name_list"] for item in by_fab["items"]
    )
