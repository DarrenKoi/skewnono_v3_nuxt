"""tool_files HTTP contract, driven through the Flask test client on mock.

The mock stands in for the tool's FTP server itself (providers/mock.py), so
these exercise the real resolution, path checks and error mapping.
"""

from collections import Counter

import pytest

from backend import create_app
from backend.ebeam._tool_specs import SLUG_TO_TOOL_TYPE, model_to_tool_type
from backend.ebeam.tool_files.paths import readable_name
from backend.sem_list.providers.mock import get_sem_list

_SLUG_OF = {tool_type: slug for slug, tool_type in SLUG_TO_TOOL_TYPE.items()}


def _unique_rows():
    rows = get_sem_list()
    counts = Counter(row["eqp_id"] for row in rows)
    return [row for row in rows if counts[row["eqp_id"]] == 1]


def _tool(tool_type, available="On"):
    return next(
        row
        for row in _unique_rows()
        if model_to_tool_type(row["eqp_model_cd"]) == tool_type
        and row["available"] == available
    )


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _list(client, row, slug="cdsem", path=None):
    query = {"fab": row["fab_name"], "eqp_id": row["eqp_id"]}
    if path is not None:
        query["path"] = path
    return client.get(f"/api/{slug}/tool-files/list", query_string=query)


def test_admin_lists_the_login_directory_of_a_cdsem_tool(client):
    response = _list(client, _tool("cd-sem"))

    assert response.status_code == 200
    body = response.get_json()
    assert body["root"] == "/"
    assert body["path"] == "/"
    assert body["parent"] is None
    assert body["max_bytes"] == 100 * 1024 * 1024
    assert [(e["name"], e["is_dir"]) for e in body["entries"]] == [
        ("DUMP", True),
        ("LOG", True),
        ("RECIPE", True),
        ("README.TXT", False),
        ("측정결과.csv", False),
        ("\xff\xfe_scan.log", False),
    ]


def _as_member(client, empno="12345"):
    client.set_cookie("LASTUSER", empno)


def test_a_non_admin_is_refused_before_any_ftp_session(client, monkeypatch):
    def no_ftp(_tool):
        raise AssertionError("FTP must not be touched for a refused caller")

    monkeypatch.setattr("backend.ebeam.tool_files.routes.open_client", no_ftp)
    _as_member(client)

    response = _list(client, _tool("cd-sem"))

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_access_reports_granted_for_the_admin_and_none_for_a_member(client):
    assert client.get("/api/tool-files/access").get_json() == {
        "verdict": "granted",
        "can_write": False,
    }
    _as_member(client)
    assert client.get("/api/tool-files/access").get_json() == {
        "verdict": "none",
        "can_write": False,
    }


def test_a_subfolder_listing_hides_links_and_carries_its_breadcrumb(client):
    body = _list(client, _tool("cd-sem"), path="/RECIPE").get_json()

    assert body["parent"] == "/"
    assert body["crumbs"] == [
        {"name": "/", "path": "/"},
        {"name": "RECIPE", "path": "/RECIPE"},
    ]
    names = [e["name"] for e in body["entries"]]
    assert "CURRENT" not in names
    assert names[:2] == ["RCP_001.rcp", "RCP_002.rcp"]
    assert body["entries"][0]["size"] == 4096
    assert body["entries"][0]["modified"] == "2026-10-15T18:00:00+09:00"


def test_an_empty_folder_lists_no_entries(client):
    body = _list(client, _tool("cd-sem"), path="/LOG/ARCHIVE").get_json()
    assert body["entries"] == []
    assert body["parent"] == "/LOG"


def test_an_hvsem_login_directory_below_slash_is_the_root(client):
    row = _tool("hv-sem")
    body = _list(client, row, slug="hvsem").get_json()
    assert (body["root"], body["path"], body["parent"]) == ("/home/hitachi", "/home/hitachi", None)
    assert body["crumbs"] == [{"name": "/home/hitachi", "path": "/home/hitachi"}]
    assert body["entries"][0]["path"] == "/home/hitachi/DUMP"


def _download(client, row, path, slug="cdsem"):
    return client.get(
        f"/api/{slug}/tool-files/download",
        query_string={"fab": row["fab_name"], "eqp_id": row["eqp_id"], "path": path},
    )


def test_download_returns_the_file_as_an_attachment(client):
    response = _download(client, _tool("cd-sem"), "/DUMP/small.bin")

    assert response.status_code == 200
    assert len(response.data) == 2048
    assert response.data.startswith(b"mock /DUMP/small.bin\n")
    assert response.headers["Content-Type"] == "application/octet-stream"
    assert response.headers["Content-Disposition"] == (
        "attachment; filename=\"small.bin\"; filename*=UTF-8''small.bin"
    )
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_a_filename_with_corrupted_bytes_round_trips_from_listing_to_download(client):
    row = _tool("cd-sem")
    entries = _list(client, row).get_json()["entries"]
    key = next(e["path"] for e in entries if e["name"].endswith(".csv"))

    assert key == "/" + "측정결과.csv".encode("utf-8").decode("latin-1")

    response = _download(client, row, key)

    assert response.status_code == 200
    assert len(response.data) == 1234
    assert response.headers["Content-Disposition"].endswith(
        "filename*=UTF-8''%EC%B8%A1%EC%A0%95%EA%B2%B0%EA%B3%BC.csv"
    )


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        ("README.TXT", "README.TXT"),
        ("측정결과.csv".encode("utf-8").decode("latin-1"), "측정결과.csv"),
        ("측정결과.csv".encode("cp949").decode("latin-1"), "측정결과.csv"),
        # Bytes valid in neither codec (the office's corrupted names) stay as read.
        ("\xff\xfe.log", "\xff\xfe.log"),
        # Already decoded by a utf-8 session: nothing to undo.
        ("측정결과.csv", "측정결과.csv"),
    ],
)
def test_readable_name_undoes_a_latin1_read(raw, shown):
    assert readable_name(raw) == shown


@pytest.mark.parametrize(
    "path",
    [
        "RECIPE",
        "/RECIPE/../..",
        "/./RECIPE",
        "//RECIPE",
        "/RECIPE/",
        "/RECIPE\\x",
        "/RECIPE\nx",
        "/C:/Windows",
    ],
)
def test_path_keys_that_break_the_rules_are_refused(client, path):
    response = _list(client, _tool("cd-sem"), path=path)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "bad_path"


@pytest.mark.parametrize("path", ["/", "/home", "/home/hitachi2"])
def test_paths_outside_the_login_directory_are_refused(client, path):
    response = _list(client, _tool("hv-sem"), slug="hvsem", path=path)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "bad_path"


def _code(response):
    return response.status_code, response.get_json()["error"]["code"]


def test_an_unknown_eqp_id_is_404(client):
    response = client.get(
        "/api/cdsem/tool-files/list", query_string={"fab": "R3", "eqp_id": "NOPE999"}
    )
    assert _code(response) == (404, "tool_not_found")


def test_an_eqp_id_on_two_different_rows_is_409(client):
    rows = get_sem_list()
    counts = Counter(row["eqp_id"] for row in rows)
    dup = next(row for row in rows if counts[row["eqp_id"]] > 1)
    slug = _SLUG_OF[model_to_tool_type(dup["eqp_model_cd"])]
    assert _code(_list(client, dup, slug=slug)) == (409, "tool_ambiguous")


def test_a_tool_asked_for_under_the_wrong_family_or_fab_is_400(client):
    row = _tool("hv-sem")
    assert _code(_list(client, row, slug="cdsem")) == (400, "tool_mismatch")
    wrong_fab = {**row, "fab_name": "NOFAB"}
    assert _code(_list(client, wrong_fab, slug="hvsem")) == (400, "tool_mismatch")


def test_missing_query_parameters_are_400(client):
    response = client.get("/api/cdsem/tool-files/list")
    assert _code(response) == (400, "bad_request")


def test_a_file_over_the_download_cap_is_413(client):
    response = _download(client, _tool("cd-sem"), "/DUMP/core_full.bin")
    assert _code(response) == (413, "too_large")


def test_a_folder_over_the_listing_cap_is_413(client, monkeypatch):
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_MAX_ENTRIES", "100")
    response = _list(client, _tool("cd-sem"), path="/LOG")
    assert _code(response) == (413, "listing_too_large")


def test_a_missing_file_is_404_file_unavailable(client):
    response = _download(client, _tool("cd-sem"), "/DUMP/gone.bin")
    assert _code(response) == (404, "file_unavailable")


def test_a_tool_that_never_answers_is_503(client):
    off = next(row for row in _unique_rows() if row["available"] == "Off")
    slug = _SLUG_OF[model_to_tool_type(off["eqp_model_cd"])]
    assert _code(_list(client, off, slug=slug)) == (503, "tool_unreachable")


def _undecodable(*_args, **_kwargs):
    raise UnicodeDecodeError("utf-8", b"\xc3", 0, 1, "invalid continuation byte")


@pytest.mark.parametrize("method", ["__enter__", "list_details"])
def test_names_the_server_cannot_decode_are_502_tool_encoding(client, monkeypatch, method):
    from backend.ebeam.tool_files.providers import mock

    monkeypatch.setattr(mock.MockFtpClient, method, _undecodable)

    response = _list(client, _tool("cd-sem"))

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "tool_encoding"
    assert "SKEWNONO_TOOL_FTP_ENCODING" in response.get_json()["error"]["message"]
