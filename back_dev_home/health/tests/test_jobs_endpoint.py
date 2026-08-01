"""The scheduler run-log endpoint.

Deliberately admin-gated like /health/providers and /health/logging: it names
internal job ids and timings, an operator's signal rather than a normal
user's. Reads app.extensions["scheduler_run_log"] directly (Task 9's carve-out)
rather than through health/data.py's mock/office swap -- this is introspection
of the running process, not phase-swappable data.
"""

import pytest

from back_dev_home import create_app
from back_dev_home._scheduler.runlog import MemoryRunLog


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    app = create_app()
    app.testing = True
    run_log = MemoryRunLog(max_records=10)
    run_log.record("image_cache_purge", "start")
    run_log.record("image_cache_purge", "end", duration_ms=12)
    app.extensions["scheduler_run_log"] = run_log
    return app.test_client()


def _admin(client, path):
    # local-dev is the admin identity at home; digits are a normal user.
    client.set_cookie("LASTUSER", "local-dev")
    return client.get(path)


def test_returns_records_newest_first(client):
    response = _admin(client, "/api/health/jobs")
    assert response.status_code == 200
    records = response.get_json()["records"]
    assert [r["event"] for r in records] == ["end", "start"]
    assert records[0]["job"] == "image_cache_purge"


def test_limit_is_honoured(client):
    records = _admin(client, "/api/health/jobs?limit=1").get_json()["records"]
    assert len(records) == 1


def test_limit_is_capped_at_the_retention_maximum(client):
    # The cap is defined by the storage layer, not mirrored in the query.
    body = _admin(client, "/api/health/jobs?limit=99999").get_json()
    assert body["limit"] <= 500


def test_garbage_limit_falls_back_to_the_default(client):
    body = _admin(client, "/api/health/jobs?limit=soon").get_json()
    assert body["limit"] == 200


def test_missing_run_log_answers_an_empty_list(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    app = create_app()
    app.testing = True
    app.extensions.pop("scheduler_run_log", None)
    client = app.test_client()
    client.set_cookie("LASTUSER", "local-dev")
    response = client.get("/api/health/jobs")
    assert response.status_code == 200
    assert response.get_json()["records"] == []


def test_normal_user_is_refused(client):
    client.set_cookie("LASTUSER", "1234567")
    response = client.get("/api/health/jobs")
    assert response.status_code in (401, 403)
