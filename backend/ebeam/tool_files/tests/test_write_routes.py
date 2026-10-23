"""Upload and delete, off by default, driven through the Flask test client on mock.

The ON path runs here on purpose: the flag ships off, and code nobody runs
rots. Refusals are proved to happen before the body is read and before any
FTP session opens.
"""

import io

import pytest

from backend import create_app
from backend.ebeam._tool_specs import model_to_tool_type
from backend.sem_list.providers.mock import get_sem_list

_ROUTES = "backend.ebeam.tool_files.routes"


def _row():
    rows = get_sem_list()
    return next(
        row
        for row in rows
        if model_to_tool_type(row["eqp_model_cd"]) == "cd-sem"
        and row["available"] == "On"
        and sum(r["eqp_id"] == row["eqp_id"] for r in rows) == 1
    )


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def fresh_tree(monkeypatch):
    """Writes land in the mock's module-level tree; each test gets its own."""
    from backend.ebeam.tool_files.providers import mock

    monkeypatch.setattr(mock, "_TREE", mock._tree())


@pytest.fixture
def write_on(monkeypatch):
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_WRITE", "1")


class _UnreadableBody(io.RawIOBase):
    def readable(self):
        return True

    def readinto(self, _buffer):
        raise AssertionError("a refused write must not read the request body")


@pytest.fixture
def untouchable(monkeypatch):
    """No body read and no FTP session for whatever request comes next."""

    def no_ftp(_tool):
        raise AssertionError("a refused write must not open FTP")

    monkeypatch.setattr(f"{_ROUTES}.open_client", no_ftp)
    return {"wsgi.input": _UnreadableBody()}


def _form(name="hello.txt", data=b"hello", dir_="/LOG/ARCHIVE"):
    row = _row()
    return {
        "fab": row["fab_name"],
        "eqp_id": row["eqp_id"],
        "dir": dir_,
        "file": (io.BytesIO(data), name),
    }


def _upload(client, environ=None, **form):
    return client.post(
        "/api/cdsem/tool-files/upload",
        data=_form(**form),
        content_type="multipart/form-data",
        environ_overrides=environ or {},
    )


def _delete(client, path, environ=None):
    row = _row()
    body = {"fab": row["fab_name"], "eqp_id": row["eqp_id"], "path": path}
    return client.post(
        "/api/cdsem/tool-files/delete", json=body, environ_overrides=environ or {}
    )


def _code(response):
    return response.status_code, response.get_json()["error"]["code"]


def _names(client, path="/LOG/ARCHIVE"):
    row = _row()
    response = client.get(
        "/api/cdsem/tool-files/list",
        query_string={"fab": row["fab_name"], "eqp_id": row["eqp_id"], "path": path},
    )
    return [e["name"] for e in response.get_json()["entries"]]


def test_with_the_flag_off_writes_are_403_write_disabled_unread(client, untouchable):
    assert _code(_upload(client, untouchable)) == (403, "write_disabled")
    assert _code(_delete(client, "/README.TXT", untouchable)) == (403, "write_disabled")


def test_with_the_flag_on_a_non_admin_is_403_forbidden_unread(client, write_on, untouchable):
    client.set_cookie("LASTUSER", "1000001")
    assert _code(_upload(client, untouchable)) == (403, "forbidden")
    assert _code(_delete(client, "/README.TXT", untouchable)) == (403, "forbidden")


def test_a_transport_that_cannot_write_is_501_unread(client, write_on, untouchable, monkeypatch):
    monkeypatch.setattr(f"{_ROUTES}.transport_supports_write", lambda: False)
    assert _code(_upload(client, untouchable)) == (501, "write_not_supported")
    assert _code(_delete(client, "/README.TXT", untouchable)) == (501, "write_not_supported")
    assert client.get("/api/tool-files/access").get_json()["can_write"] is False


def _can_write(client):
    return client.get("/api/tool-files/access").get_json()["can_write"]


def test_can_write_needs_the_flag_and_an_admin(client, monkeypatch):
    assert _can_write(client) is False
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_WRITE", "true")
    assert _can_write(client) is True
    client.set_cookie("LASTUSER", "1000001")
    assert _can_write(client) is False


def test_an_admin_upload_appears_in_the_listing_with_its_bytes(client, write_on):
    response = _upload(client, name="hello.txt", data=b"hello tool")

    assert response.status_code == 201
    assert response.get_json() == {"path": "/LOG/ARCHIVE/hello.txt"}
    assert _names(client) == ["hello.txt"]
    row = _row()
    download = client.get(
        "/api/cdsem/tool-files/download",
        query_string={"fab": row["fab_name"], "eqp_id": row["eqp_id"],
                      "path": "/LOG/ARCHIVE/hello.txt"},
    )
    assert download.data == b"hello tool"


def test_uploading_onto_an_existing_name_is_409_and_keeps_the_original(client, write_on):
    assert _upload(client, data=b"first").status_code == 201

    assert _code(_upload(client, data=b"second")) == (409, "file_exists")
    row = _row()
    kept = client.get(
        "/api/cdsem/tool-files/download",
        query_string={"fab": row["fab_name"], "eqp_id": row["eqp_id"],
                      "path": "/LOG/ARCHIVE/hello.txt"},
    )
    assert kept.data == b"first"


def test_delete_makes_a_file_disappear_from_the_listing(client, write_on):
    assert "README.TXT" in _names(client, "/")

    response = _delete(client, "/README.TXT")

    assert response.status_code == 200
    assert response.get_json() == {"deleted": "/README.TXT"}
    assert "README.TXT" not in _names(client, "/")
    assert _code(_delete(client, "/README.TXT")) == (404, "file_unavailable")


def test_delete_refuses_a_path_outside_the_root(client, write_on):
    assert _code(_delete(client, "/LOG/../README.TXT")) == (400, "bad_path")
    assert "README.TXT" in _names(client, "/")


def test_a_content_length_over_the_cap_is_413_before_parsing(
    client, write_on, untouchable, monkeypatch
):
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_MAX_UPLOAD_BYTES", "1000")
    response = _upload(client, untouchable, data=b"x" * 2000)
    assert _code(response) == (413, "too_large")


def test_a_body_without_content_length_is_still_counted_against_the_cap(
    client, write_on, monkeypatch
):
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_MAX_UPLOAD_BYTES", "1000")
    chunked = {"CONTENT_LENGTH": "", "wsgi.input_terminated": True}

    response = _upload(client, chunked, data=b"x" * 2000)

    assert _code(response) == (413, "too_large")
    assert _names(client) == []


@pytest.mark.parametrize("name", ["../../evil.txt", "C:\\Users\\me\\evil.txt", "a/b/evil.txt"])
def test_an_upload_keeps_only_the_basename(client, write_on, name):
    response = _upload(client, name=name)
    assert response.get_json() == {"path": "/LOG/ARCHIVE/evil.txt"}
    assert _names(client) == ["evil.txt"]


@pytest.mark.parametrize(
    ("name", "dir_"), [("..", "/LOG/ARCHIVE"), ("ok.txt", "/LOG/../RECIPE"), ("ok.txt", "LOG")]
)
def test_an_upload_target_that_breaks_the_path_rules_is_400(client, write_on, name, dir_):
    assert _code(_upload(client, name=name, dir_=dir_)) == (400, "bad_path")


def test_a_lost_rename_reply_is_503_transfer_uncertain(client, write_on, monkeypatch):
    from ftp_handler.core import TransferUncertain

    from backend.ebeam.tool_files.providers import mock

    def lost(self, remote_path, data, *, deadline=None):
        raise TransferUncertain("reply lost", temp_path=f"{remote_path}.x.part")

    monkeypatch.setattr(mock.MockFtpClient, "put", lost)
    response = _upload(client)
    assert _code(response) == (503, "transfer_uncertain")
    # The temp name is the server's business, not the page's.
    assert ".part" not in response.get_json()["error"]["message"]


def test_writes_are_logged_with_actor_source_target_and_result(client, write_on, caplog):
    caplog.set_level("INFO", logger="skewnono.tool_files")
    row = _row()
    _upload(client)
    _upload(client)
    _delete(client, "/LOG/ARCHIVE/hello.txt")

    lines = [r.getMessage() for r in caplog.records if r.name == "skewnono.tool_files"]
    # The host IP names the disk: Provision has two under one eqp_id.
    target = f"{row['eqp_id']}@{row['fab_name']}/{row['eqp_ip']}:/LOG/ARCHIVE"
    assert [line.split(" request_id=")[0] for line in lines] == [
        f"tool_files upload actor=local-dev source=local target={target}/hello.txt result=ok",
        f"tool_files upload actor=local-dev source=local target={target}/hello.txt result=file_exists",
        f"tool_files delete actor=local-dev source=local target={target}/hello.txt result=ok",
    ]


def test_two_files_in_one_upload_are_400(client, write_on):
    row = _row()
    response = client.post(
        "/api/cdsem/tool-files/upload",
        data={
            "fab": row["fab_name"],
            "eqp_id": row["eqp_id"],
            "dir": "/LOG/ARCHIVE",
            "file": [(io.BytesIO(b"a"), "a.txt"), (io.BytesIO(b"b"), "b.txt")],
        },
        content_type="multipart/form-data",
    )
    assert _code(response) == (400, "bad_request")
    assert _names(client) == []


def test_a_name_the_tool_encoding_cannot_carry_is_400(client, write_on, monkeypatch):
    from backend.ebeam.tool_files.providers import mock

    def latin1_only(self, remote_path, data, *, deadline=None):
        remote_path.encode("latin-1")

    monkeypatch.setattr(mock.MockFtpClient, "put", latin1_only)
    assert _code(_upload(client, name="측정.csv")) == (400, "name_unencodable")
