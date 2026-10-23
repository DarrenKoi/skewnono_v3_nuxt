"""FTP 접속 for the AMAT families: their accounts, and Provision's two hosts.

VeritySEM has one host (tool IP == data IP). Provision has the tool (eqp_ip)
and a separate data host (data_ip); the caller picks one with ``host``.
"""

import pytest

from backend import create_app
from backend.ebeam._tool_specs import model_to_tool_type
from backend.sem_list.providers.mock import get_sem_list

_ACCOUNTS = "VERITYSEM=rtauser:**csbm21,PROVISION=wf:wfuser"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SKEWNONO_TOOL_FTP_ACCOUNTS", _ACCOUNTS)
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def opened(monkeypatch):
    """The Tool each FTP session was opened for."""
    from backend.ebeam.tool_files import routes

    seen = []
    real = routes.open_client

    def spy(tool):
        seen.append(tool)
        return real(tool)

    monkeypatch.setattr(routes, "open_client", spy)
    return seen


def _row(tool_type, **match):
    return next(
        row
        for row in get_sem_list()
        if model_to_tool_type(row["eqp_model_cd"]) == tool_type
        and all(row.get(k) == v for k, v in match.items())
    )


def _list(client, slug, row, **extra):
    query = {"fab": row["fab_name"], "eqp_id": row["eqp_id"], **extra}
    return client.get(f"/api/{slug}/tool-files/list", query_string=query)


def test_a_veritysem_tool_lists_with_its_own_account(client, opened):
    row = _row("veritysem", data_available="On", tool_available="On")

    response = _list(client, "veritysem", row)

    assert response.status_code == 200
    assert (opened[0].host, opened[0].user, opened[0].password) == (
        row["eqp_ip"], "rtauser", "**csbm21"
    )


def test_a_provision_tool_opens_its_tool_ip_by_default(client, opened):
    row = _row("provision", tool_available="On")

    response = _list(client, "provision", row)

    assert response.status_code == 200
    assert (opened[0].host, opened[0].user, opened[0].password) == (row["eqp_ip"], "wf", "wfuser")


def test_host_data_opens_the_provision_data_ip_with_the_same_account(client, opened):
    row = _row("provision", data_available="On")

    response = _list(client, "provision", row, host="data")

    assert response.status_code == 200
    assert row["data_ip"] != row["eqp_ip"]
    assert (opened[0].host, opened[0].user) == (row["data_ip"], "wf")


def test_each_provision_host_answers_by_its_own_probe(client):
    tool_down = _row("provision", tool_available="Off", data_available="On")

    assert _list(client, "provision", tool_down).status_code == 503
    assert _list(client, "provision", tool_down, host="data").status_code == 200


@pytest.mark.parametrize("slug,tool_type", [("cdsem", "cd-sem"), ("veritysem", "veritysem")])
def test_host_data_is_refused_for_a_family_without_a_separate_data_host(client, slug, tool_type):
    response = _list(client, slug, _row(tool_type), host="data")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "bad_request"


def test_an_unknown_host_is_400(client):
    response = _list(client, "provision", _row("provision"), host="nas")

    assert response.status_code == 400
