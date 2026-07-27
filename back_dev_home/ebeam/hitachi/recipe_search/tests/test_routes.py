import logging

from flask import Flask, g

from back_dev_home._logging import activity as activity_mod
from back_dev_home.ebeam.hitachi.recipe_search import routes


def test_compare_promotes_body_fab_without_logging_the_body(
    monkeypatch,
):
    monkeypatch.setattr(activity_mod, "install_opensearch_logging", lambda: None)
    monkeypatch.setattr(activity_mod, "record_request", lambda *_args: None)
    monkeypatch.setattr(
        routes,
        "get_recipe_compare_data",
        lambda *_args: {"tool_type": "cd-sem", "recipes": []},
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
            json={"fab_name": "m14", "recipe_names": ["R1", "R2"]},
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
        assert "recipe_names" not in record.__dict__
        assert "R1" not in repr(record.__dict__)
        assert "R2" not in repr(record.__dict__)
    finally:
        logger.handlers[:] = saved[0]
        logger.setLevel(saved[1])
        logger.propagate = saved[2]
