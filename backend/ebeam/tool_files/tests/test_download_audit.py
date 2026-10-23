"""Every download leaves an audit line per file (user-confirmed 2026-10-23: 감사용).

The line is the same ``skewnono.tool_files`` line uploads and deletes write,
so it reaches OpenSearch through the root handler with no index change.
"""

import re

import pytest

from backend import create_app
from backend.ebeam._tool_specs import model_to_tool_type
from backend.sem_list.providers.mock import get_sem_list


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def lines(caplog):
    caplog.set_level("INFO", logger="skewnono.tool_files")
    return lambda: [
        r.getMessage() for r in caplog.records
        if r.name == "skewnono.tool_files" and r.getMessage().startswith("tool_files download ")
    ]


def _row():
    return next(
        r for r in get_sem_list()
        if model_to_tool_type(r["eqp_model_cd"]) == "cd-sem" and r["available"] == "On"
        and sum(x["eqp_id"] == r["eqp_id"] for x in get_sem_list()) == 1
    )


def _field(line, name):
    return re.search(rf"\b{name}=(\S+)", line).group(1)


def test_a_download_is_audited_with_its_host_path_and_bytes(client, lines):
    row = _row()
    response = client.get(
        "/api/cdsem/tool-files/download",
        query_string={"fab": row["fab_name"], "eqp_id": row["eqp_id"], "path": "/README.TXT"},
    )

    assert response.status_code == 200
    [line] = lines()
    assert _field(line, "actor") == "local-dev"
    assert _field(line, "target") == f"{row['eqp_id']}@{row['fab_name']}/{row['eqp_ip']}:/README.TXT"
    assert (_field(line, "result"), _field(line, "bytes")) == ("ok", "512")


def test_a_failed_download_is_audited_with_its_code(client, lines):
    row = _row()
    client.get(
        "/api/cdsem/tool-files/download",
        query_string={"fab": row["fab_name"], "eqp_id": row["eqp_id"], "path": "/NOPE.TXT"},
    )

    [line] = lines()
    assert _field(line, "result") == "file_unavailable"
    assert "bytes=" not in line


def _zip(client, row, paths):
    return client.post(
        "/api/cdsem/tool-files/download-zip",
        json={"fab": row["fab_name"], "eqp_id": row["eqp_id"], "paths": paths},
    )


def test_a_zip_is_audited_once_per_file_under_one_request_id(client, lines):
    row = _row()
    assert _zip(client, row, ["/README.TXT", "/DUMP/small.bin"]).status_code == 200

    found = lines()
    assert [(_field(x, "target").rsplit(":", 1)[1], _field(x, "result"), _field(x, "bytes")) for x in found] == [
        ("/README.TXT", "ok", "512"),
        ("/DUMP/small.bin", "ok", "2048"),
    ]
    assert len({_field(x, "request_id") for x in found}) == 1


def test_a_zip_that_fails_audits_every_file_with_the_failure(client, lines, monkeypatch):
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_MAX_BYTES", "1000")
    row = _row()
    assert _zip(client, row, ["/README.TXT", "/DUMP/small.bin"]).status_code == 413

    # README.TXT was fetched, but the zip never left: nothing reads "ok".
    assert [(_field(x, "result"), "bytes=" in x) for x in lines()] == [
        ("batch_too_large", False),
        ("batch_too_large", False),
    ]
