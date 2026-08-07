"""The member-name join on the admin log page.

The join lives in the route rather than a provider because OpenSearch stores
employee numbers and no names — see activity/routes.py, which made the same
call for the same reason. These pin that a directory that cannot answer costs
the names and never the rows.
"""

import pytest
from flask import Flask, g

from back_dev_home._auth.directory import bare_member
from back_dev_home._auth.provider import SOURCE_LOCAL
from back_dev_home._core.contract_check import assert_matches
from back_dev_home.admin_logs import routes
from back_dev_home.admin_logs.contracts import NamedLogQueryResponse


def _item(user_id):
    """A full LogItem — every key is part of the contract, values may be None."""
    return {
        "id": f"doc-{user_id}",
        "index": "skewnono_log_local-2026.08.07",
        "timestamp": "2026-08-07T04:00:00Z",
        "level": "INFO",
        "event": "request",
        "logger": "skewnono.activity",
        "user_id": user_id,
        "method": "GET",
        "path": "/api/sem-list",
        "status": 200,
        "latency_ms": 12,
        "feature": "sem_list",
        "message": None,
        "exception": None,
        "raw": {"user_id": user_id},
    }


def _page(*user_ids):
    return {
        "generated_at": "2026-08-07T04:00:00Z",
        "page": 1,
        "page_size": 50,
        "total": len(user_ids),
        "page_count": 1,
        "filters": {},
        "items": [_item(user_id) for user_id in user_ids],
    }


@pytest.fixture
def make_client(monkeypatch):
    """Client factory with a stubbed provider, a stubbed directory, and admin."""

    monkeypatch.delenv("SKEWNONO_ADMIN_USERS", raising=False)

    def build(page, members):
        """``members`` is the directory's answer: a dict, or a callable taking
        the ids it was asked about (for the test that inspects them)."""
        resolve = members if callable(members) else (lambda ids: members)
        monkeypatch.setattr(routes, "query_logs", lambda params: page)
        monkeypatch.setattr(routes, "lookup_members", resolve)

        app = Flask(__name__)

        @app.before_request
        def identity():
            # local-dev is the home default admin; `local` is a trusted source.
            g.user_id = "local-dev"
            g.identity_source = SOURCE_LOCAL

        app.register_blueprint(routes.bp, url_prefix="/api")
        return app.test_client()

    return build


def _named(empno, name):
    return {**bare_member(empno), "emp_nm": name}


def test_named_users_are_carried_in_a_sibling_map(make_client):
    client = make_client(
        _page("2067928", "1234567"),
        {"2067928": _named("2067928", "고대영"), "1234567": _named("1234567", "홍길동")},
    )

    payload = client.get("/api/admin/logs").get_json()

    assert payload["members"] == {"2067928": "고대영", "1234567": "홍길동"}
    assert_matches(payload, NamedLogQueryResponse)


def test_the_name_stays_out_of_the_row_and_out_of_raw(make_client):
    """LogItem is the OpenSearch document. A joined name must not look like one."""
    client = make_client(
        _page("2067928"), {"2067928": _named("2067928", "고대영")}
    )

    item = client.get("/api/admin/logs").get_json()["items"][0]

    assert "emp_nm" not in item
    assert "emp_nm" not in item["raw"]


def test_unnamed_employees_are_omitted_rather_than_mapped_to_none(make_client):
    """The caller falls back to the number, so an entry would say nothing.

    Ordinary, not exceptional: contractors and service accounts hold a
    LASTUSER cookie with no directory row.
    """
    client = make_client(_page("9999999"), {"9999999": bare_member("9999999")})

    payload = client.get("/api/admin/logs").get_json()

    assert payload["members"] == {}
    assert len(payload["items"]) == 1


def test_a_directory_outage_costs_the_names_and_not_the_rows(make_client):
    """lookup_members degrades to bare rows rather than raising."""
    client = make_client(
        _page("2067928", "1234567"),
        {"2067928": bare_member("2067928"), "1234567": bare_member("1234567")},
    )

    payload = client.get("/api/admin/logs").get_json()

    assert payload["members"] == {}
    assert payload["total"] == 2
    assert len(payload["items"]) == 2


def test_rows_without_a_user_id_do_not_reach_the_directory(make_client):
    """Anonymous rows are ordinary. Asking about None would be a wasted lookup."""
    asked = []

    def record(ids):
        asked.extend(ids)
        return {}

    client = make_client(_page(None, "2067928"), record)

    payload = client.get("/api/admin/logs").get_json()

    assert asked == ["2067928"]
    assert payload["members"] == {}
