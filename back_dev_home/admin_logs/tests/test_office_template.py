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
