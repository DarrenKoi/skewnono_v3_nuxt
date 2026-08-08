import logging

import pytest
from flask import Flask, g

from back_dev_home._logging import activity as activity_mod
from back_dev_home.ebeam.recipe_search import routes


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/api")
    return app.test_client()


def test_recipes_route_parses_comma_fab_list(client):
    res = client.get("/api/cdsem/recipe-search/recipes?fab_name=r3,m16b")
    assert res.status_code == 200
    body = res.get_json()
    assert body["fab_names"] == ["R3", "M16B"]
    assert {row["fab_name"] for row in body["rows"]} == {"R3", "M16B"}


def test_compare_promotes_body_fab_without_logging_the_body(
    monkeypatch,
):
    monkeypatch.setattr(activity_mod, "install_opensearch_logging", lambda: None)
    monkeypatch.setattr(activity_mod, "record_request", lambda *_args: None)
    monkeypatch.setattr(
        routes,
        "get_recipe_compare_data",
        lambda *_args: {"tool_type": "cd-sem", "fab_names": [], "recipes": []},
    )

    logger = logging.getLogger("skewnono.activity")
    saved = (list(logger.handlers), logger.level, logger.propagate)
    try:
        logger.handlers[:] = []
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
        records: list[logging.LogRecord] = []

        class _Sink(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        app = Flask(__name__)

        @app.before_request
        def _identity():
            g.user_id = "u1"

        app.register_blueprint(routes.bp, url_prefix="/api")
        activity_mod.install_activity_logging(app)
        logger.addHandler(_Sink())

        response = app.test_client().post(
            "/api/cdsem/recipe-search/compare",
            json={"recipes": [
                {"recipe_name": "R1", "fab_name": "m14"},
                {"recipe_name": "R2", "fab_name": "m14"},
            ]},
        )

        assert response.status_code == 200
        request_records = [
            record
            for record in records
            if getattr(record, "event", None) == "request"
        ]
        assert len(request_records) == 1
        record = request_records[0]
        assert record.fab_name_list == ["M14"]
        assert record.query_string == ""
        assert "recipes" not in record.__dict__
        assert "R1" not in repr(record.__dict__)
        assert "R2" not in repr(record.__dict__)
    finally:
        logger.handlers[:] = saved[0]
        logger.setLevel(saved[1])
        logger.propagate = saved[2]


def test_compare_route_takes_per_recipe_fabs(client):
    res = client.post("/api/cdsem/recipe-search/compare", json={
        "recipes": [
            {"recipe_name": "A/B_ABC123_STD_00001", "fab_name": "r3"},
            {"recipe_name": "A/B_ABC123_STD_00001", "fab_name": "m16b"},
        ]
    })
    assert res.status_code == 200
    body = res.get_json()
    assert body["fab_names"] == ["R3", "M16B"]


def test_compare_route_rejects_legacy_body(client):
    res = client.post("/api/cdsem/recipe-search/compare", json={
        "recipe_names": ["A"], "fab_name": "R3"
    })
    assert res.status_code == 400
