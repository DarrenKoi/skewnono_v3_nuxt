"""Route-level gate for sem_list.

The pending endpoint is separate from /api/sem-list on purpose: six features
resolve eqp_id -> eqp_ip through the roster response, so unreachable tools
must never appear there.
"""

from back_dev_home import create_app


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_pending_endpoint_returns_rows():
    response = _client().get("/api/sem-list/pending")

    assert response.status_code == 200
    rows = response.get_json()
    assert isinstance(rows, list)
    assert rows
    assert set(rows[0]) == {
        "fac_id", "eqp_id", "eqp_model_cd", "eqp_grp_id",
        "vendor_nm", "eqp_ip", "fab_name", "updt_dt",
    }


def test_pending_endpoint_never_leaks_into_the_roster_endpoint():
    client = _client()
    roster = {row["eqp_id"] for row in client.get("/api/sem-list").get_json()}
    pending = {row["eqp_id"] for row in client.get("/api/sem-list/pending").get_json()}

    assert roster & pending == set()
