"""The office template: a direct FtpClient, or the read-only proxy on Windows."""

import pytest
from ftp_handler.core import FtpClient
from ftp_handler.proxy import FtpClient as ProxyFtpClient

from backend.ebeam.tool_files.providers import mock
from backend.ebeam.tool_files.providers import office_example as office
from backend.ebeam.tool_files.resolve import Tool


def test_open_client_builds_a_direct_ftp_client_for_the_resolved_tool():
    tool = Tool(
        eqp_id="HCDX303",
        fab_name="M11A",
        tool_type="cd-sem",
        host="10.0.0.7",
        user="verity",
        password="pw",
        port=2121,
        timeout=8.0,
        encoding="latin-1",
    )

    client = office.open_client(tool)

    assert isinstance(client, FtpClient)
    assert (client.host, client.user, client.password, client.port, client.timeout, client.encoding) == (
        "10.0.0.7",
        "verity",
        "pw",
        2121,
        8.0,
        "latin-1",
    )


def test_windows_reaches_tools_through_the_read_only_proxy(monkeypatch):
    # A Windows office PC (Phase 2) cannot open FTP to tools; msr_image's rule.
    monkeypatch.setattr("platform.system", lambda: "Windows")

    client = office.open_client(_tool())

    assert isinstance(client, ProxyFtpClient)
    assert (client.host, client.user, client.port, client.encoding) == (
        "10.0.0.7",
        "verity",
        2121,
        "latin-1",
    )
    assert office.transport_supports_write() is False


def test_anything_but_windows_opens_ftp_directly_and_may_write(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")

    assert type(office.open_client(_tool())) is FtpClient
    assert office.transport_supports_write() is True


def test_the_proxy_holds_each_transfer_to_the_proxy_deadline(monkeypatch):
    # The route asks for the direct deadline (120 s); the proxy host's
    # harakiri would kill that request first.
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_PROXY_DEADLINE", "30")
    sent = []
    monkeypatch.setattr(
        "ftp_handler.proxy.proxy_client.FtpClient.download",
        lambda self, path, *, max_bytes=None, deadline=None: sent.append(deadline),
    )
    monkeypatch.setattr(
        "ftp_handler.proxy.proxy_client.FtpClient.list_details",
        lambda self, d, pattern=None, *, deadline=None, **kw: sent.append(deadline),
    )

    with office.open_client(_tool()) as ftp:
        ftp.download("/a", max_bytes=10, deadline=120.0)
        ftp.download("/a", deadline=5.0)
        ftp.list_details("/", max_entries=3, deadline=120.0)

    assert sent == [30.0, 5.0, 30.0]


class _Canned:
    """``requests.post`` for the proxy client: records each call, answers one body."""

    def __init__(self, status, body):
        self.status_code, self._body, self.calls = status, body, []

    def __call__(self, url, json=None, headers=None, timeout=None, stream=False):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self

    def json(self):
        return self._body

    def close(self):
        pass


def test_the_proxy_home_is_a_capped_pwd_not_a_listing(monkeypatch):
    # Every /list and /download calls home() first; it must not open an
    # uncapped LIST of the home folder on the proxy host.
    monkeypatch.setattr("platform.system", lambda: "Windows")
    post = _Canned(200, {"home": "/home/verity", "entries": []})
    monkeypatch.setattr("ftp_handler.proxy.proxy_client.requests.post", post)

    with office.open_client(_tool()) as ftp:
        assert ftp.home() == "/home/verity"

    (call,) = post.calls
    assert call["json"]["home_only"] is True
    _, read = call["timeout"]
    assert read is not None and read <= 2 * _tool().timeout


def test_a_proxy_encoding_error_answers_502_tool_encoding(monkeypatch):
    from backend.ebeam.tool_files import routes
    from backend.ebeam.tool_files.errors import ToolFilesError

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr(routes, "open_client", office.open_client)
    post = _Canned(422, {"code": "encoding", "error": "'utf-8' codec can't decode byte 0xb0"})
    monkeypatch.setattr("ftp_handler.proxy.proxy_client.requests.post", post)

    with pytest.raises(ToolFilesError) as caught, routes._session(_tool()) as ftp:
        ftp.list_details("/", deadline=5.0)

    assert (caught.value.status, caught.value.code) == (502, "tool_encoding")


def test_the_mock_transport_supports_write():
    assert mock.transport_supports_write() is True


def test_the_template_offers_every_function_the_dispatcher_calls():
    surface = ("open_client", "transport_supports_write", "probe")
    assert [name for name in surface if not callable(getattr(office, name, None))] == []
    assert [name for name in surface if not callable(getattr(mock, name, None))] == []


def _tool() -> Tool:
    return Tool(
        eqp_id="HCDX303",
        fab_name="M11A",
        tool_type="cd-sem",
        host="10.0.0.7",
        user="verity",
        password="pw",
        port=2121,
        timeout=8.0,
        encoding="latin-1",
    )
