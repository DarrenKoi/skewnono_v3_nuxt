"""The proxy add-on route: fixed read-only commands, 5xx recorded, CRLF refused."""

from __future__ import annotations

import ftplib

import pytest

from scripts.probes import probe_ftp_server_info as probe


class FakeFTP:
    sent: list[str] = []

    def __init__(self, *, timeout, encoding):
        pass

    def connect(self, host, port, timeout):
        return "220 Microsoft FTP Service"

    def login(self, user, passwd):
        if passwd != "pw":
            raise ftplib.error_perm("530 User cannot log in.")

    def sendcmd(self, cmd):
        FakeFTP.sent.append(cmd)
        if cmd.startswith("AVBL"):
            return "213 123456789"
        raise ftplib.error_perm(f"500 '{cmd}': command not understood")

    def close(self):
        pass


@pytest.fixture
def client(monkeypatch):
    from flask import Flask

    monkeypatch.setattr(ftplib, "FTP", FakeFTP)
    monkeypatch.delenv("FTP_PROXY_TOKEN", raising=False)
    FakeFTP.sent = []
    app = Flask(__name__)
    app.register_blueprint(probe.ftp_server_info_sknn_v3)
    return app.test_client()


def test_route_runs_the_fixed_list_and_records_refusals(client):
    resp = client.post(probe.URL_SERVER_INFO, json={"host": "10.0.0.1", "user": "u", "password": "pw"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["welcome"].startswith("220")
    by_cmd = {r["cmd"]: r for r in body["replies"]}
    assert by_cmd["AVBL /D_Drive"] == {"cmd": "AVBL /D_Drive", "ok": True, "reply": "213 123456789"}
    assert by_cmd["SITE DF"]["ok"] is False
    assert FakeFTP.sent == [c.format(dir="/D_Drive") for c in probe.COMMANDS]


def test_crlf_in_dir_never_reaches_the_server(client):
    resp = client.post(probe.URL_SERVER_INFO, json={"host": "h", "remote_dir": "/x\r\nDELE a"})
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "bad_request"
    assert FakeFTP.sent == []


def test_bad_login_is_unreachable_and_token_is_enforced(client, monkeypatch):
    resp = client.post(probe.URL_SERVER_INFO, json={"host": "h", "user": "u", "password": "no"})
    assert resp.get_json()["code"] == "unreachable"
    monkeypatch.setenv("FTP_PROXY_TOKEN", "s3cret")
    assert client.post(probe.URL_SERVER_INFO, json={"host": "h"}).status_code == 401
