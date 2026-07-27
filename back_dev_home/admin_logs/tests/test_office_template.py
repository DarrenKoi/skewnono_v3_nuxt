import pytest
from flask import Flask, g

import ops_store
from back_dev_home.admin_logs import routes
from back_dev_home.admin_logs.providers import mock, office_example
from back_dev_home.admin_logs.query import (
    item_from_hit,
    parse_log_query,
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
        g.user_id = "local-dev"

    app.register_blueprint(routes.bp, url_prefix="/api")
    response = app.test_client().get("/api/admin/logs")

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "log_query_failed"
    assert body["error"]["message"] == "Could not query OpenSearch logs"
    assert "secret-internal-host" not in str(body)


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

    assert {"wildcard": {"error_name": "*timeout*"}} in should
    assert {"match_phrase": {"error_name": "timeout"}} not in should


def test_activity_kind_and_fab_name_narrow_the_query():
    """fab_name goes through the writer's normalize_fab_name_list, so casing
    and comma-separated input match what was actually indexed."""
    parsed = parse_log_query({"activity_kind": "feature", "fab_name": "m16b, m14"})

    filters = parsed.query["bool"]["filter"]
    assert {"term": {"activity_kind": "feature"}} in filters
    assert {"terms": {"fab_name_list": ["M16B", "M14"]}} in filters
    assert parsed.filters["activity_kind"] == "feature"
    assert parsed.filters["fab_name"] == "M16B,M14"


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
