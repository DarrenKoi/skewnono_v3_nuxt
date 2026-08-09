"""Firewall-free FTP proxy as a Flask Blueprint — server half of the proxy pair.

Runs on a host that CAN reach the equipment FTP servers. A firewalled client
POSTs download specs here; this side does the real FTP (reusing
FtpFleetDownloader) and returns the file bytes over HTTP. Pair it with
``ftp_handler/proxy/proxy_downloader.py`` on the firewalled client — same public
API, HTTP transport instead of direct FTP.

    local PC ──HTTP──> Flask app (this blueprint) ──FTP──> equipment servers
    (firewalled,        (firewall-free)                     (only reachable
     no FTP egress)                                          from the proxy)

Mount it on an EXISTING Flask app as one blueprint among many:

    from ftp_handler.proxy.flask_proxy import ftp_proxy_sknn_v3
    app.register_blueprint(ftp_proxy_sknn_v3)

Routes carry the ``_sknn_v3`` suffix so they don't collide with paths already
used by the host app:
    POST /download_sknn_v3   request JSON:
        {"port","max_concurrency","connect_timeout",
         "host_timeout","passive",
         "specs":[{"host","files":[...],"listings":[{"remote_dir","pattern"}]}]}
    200 response JSON:
        {"files":[{"host","remote_path","data_b64"}],
         "failures":[{"host","error","remote_path"}]}
    POST /size_dirs_sknn_v3  request JSON (same shape as /download_sknn_v3):
        {... ,"specs":[{"host","files":[...],"listings":[...]}]}
    200 response JSON (per-file byte counts, no file bytes):
        {"files":[{"host","remote_path","size"}],
         "failures":[{"host","error","remote_path"}]}
    POST /upload_sknn_v3     request JSON (same tuning keys):
        {"specs":[{"host","files":[{"remote_path","data_b64"}]}]}
    200 response JSON:
        {"results":[{"host","remote_path"}],
         "failures":[{"host","error","remote_path"}]}
    GET  /healthz_sknn_v3 -> {"status":"ok"}

Auth: if env FTP_PROXY_TOKEN is set, requests must carry
``Authorization: Bearer <token>`` or get 401. Always serve behind HTTPS in
production — file bytes cross this connection. The fleet's equipment FTP
credentials stay on the proxy host in ``FTP_PROXY_FTP_USER`` /
``FTP_PROXY_FTP_PASSWORD``; a spec may override them per host by sending
``user``/``password`` in its wire entry, for a fleet that spans accounts.

Standalone run (without an existing app):
    pip install flask
    set FTP_PROXY_FTP_USER=ftpuser
    set FTP_PROXY_FTP_PASSWORD=ftppass
    set FTP_PROXY_TOKEN=secret    # PowerShell: $env:FTP_PROXY_TOKEN="secret"
    python flask_proxy.py                           # serves 0.0.0.0:8080
"""

import base64
import os
from pathlib import Path

from flask import Blueprint, Flask, jsonify, request

# Import the real downloader, whether this module is run as a package member or
# copied out flat beside fleet_downloader.py and run as a script.
try:
    from ..direct_downloader.fleet_downloader import (
        FtpFleetDownloader,
        HostSpec,
        ListDir,
        UploadFile,
        UploadSpec,
    )
except ImportError:  # copied beside fleet_downloader.py and imported bare
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fleet_downloader import (
        FtpFleetDownloader,
        HostSpec,
        ListDir,
        UploadFile,
        UploadSpec,
    )

# Suffixed to avoid collisions with routes already mounted on the host app.
# Keep in sync with the paths proxy_downloader.py POSTs to.
URL_DOWNLOAD = "/download_sknn_v3"
URL_LIST = "/list_dirs_sknn_v3"
URL_SIZE = "/size_dirs_sknn_v3"
URL_UPLOAD = "/upload_sknn_v3"
URL_HEALTH = "/healthz_sknn_v3"

ftp_proxy_sknn_v3 = Blueprint("ftp_proxy_sknn_v3", __name__)


def _spec_from_wire(entry: dict) -> HostSpec:
    listings = [
        ListDir(remote_dir=item["remote_dir"], pattern=item.get("pattern"))
        for item in entry.get("listings", [])
    ]
    return HostSpec(
        host=entry["host"],
        files=list(entry.get("files", [])),
        listings=listings,
        # `.get`, never `[...]`: a client that predates per-host credentials
        # sends no such key, and that host must still resolve to the proxy's
        # own FTP_PROXY_FTP_USER rather than 500. Deploy order between the two
        # halves is not something this blueprint gets to dictate.
        user=entry.get("user"),
        password=entry.get("password"),
    )


def _upload_spec_from_wire(entry: dict) -> UploadSpec:
    # Upload data crosses the wire base64'd (it's bytes, not JSON-native); decode
    # back to raw bytes here before the STOR.
    files = [
        UploadFile(
            remote_path=item["remote_path"],
            data=base64.b64decode(item["data_b64"]),
        )
        for item in entry.get("files", [])
    ]
    return UploadSpec(
        host=entry["host"],
        files=files,
        user=entry.get("user"),
        password=entry.get("password"),
    )


def _unauthorized():
    """Return a 401 response if the request fails the bearer-token check, else
    ``None``. Token is read per request so it can be configured independently of
    when the host app (and this blueprint) were imported."""
    token = os.getenv("FTP_PROXY_TOKEN")
    if token is not None and request.headers.get("Authorization", "") != f"Bearer {token}":
        return jsonify({"error": "unauthorized"}), 401
    return None


def _downloader_from(body: dict) -> FtpFleetDownloader:
    """Build the FtpFleetDownloader from the request body's tuning.

    The FLEET's FTP credentials come from the proxy host's environment and never
    cross the client HTTP hop. They are the default, not the only source: a spec
    may carry a per-host ``user``/``password`` override (see
    ``_spec_from_wire``) for a fleet spanning accounts, and that one does travel
    in the body. Hosts on the shared account send nothing.

    The remaining tuning comes from the client so proxy-side behavior matches
    the direct adapter. host_timeout default 45s stays under the host app's
    harakiri=60 so the downloader's own backstop fires before uWSGI kills the
    request. See ADR 0001.
    """
    return FtpFleetDownloader(
        user=os.environ["FTP_PROXY_FTP_USER"],
        password=os.environ["FTP_PROXY_FTP_PASSWORD"],
        port=body.get("port", 21),
        max_concurrency=body.get("max_concurrency", 48),
        connect_timeout=body.get("connect_timeout", 8.0),
        host_timeout=body.get("host_timeout", 45.0),
        passive=body.get("passive", True),
    )


@ftp_proxy_sknn_v3.get(URL_HEALTH)
def healthz():
    return jsonify({"status": "ok"})


@ftp_proxy_sknn_v3.post(URL_DOWNLOAD)
def download():
    denied = _unauthorized()
    if denied is not None:
        return denied

    body = request.get_json(force=True)
    specs = [_spec_from_wire(entry) for entry in body.get("specs", [])]
    report = _downloader_from(body).download(specs)

    return jsonify(
        {
            "files": [
                {
                    "host": f.host,
                    "remote_path": f.remote_path,
                    "data_b64": base64.b64encode(f.data).decode("ascii"),
                }
                for f in report.files
            ],
            "failures": [
                {"host": x.host, "error": x.error, "remote_path": x.remote_path}
                for x in report.failures
            ],
        }
    )


@ftp_proxy_sknn_v3.post(URL_LIST)
def list_dirs():
    # The listing pass over HTTP: enumerate each host's `listings` dirs and
    # return discovered paths only (no file bytes), so this carries none of the
    # base64/RAM weight the download route does — ADR 0001's batch math doesn't
    # apply. Only spec.listings is consulted; spec.files is ignored.
    denied = _unauthorized()
    if denied is not None:
        return denied

    body = request.get_json(force=True)
    specs = [_spec_from_wire(entry) for entry in body.get("specs", [])]
    report = _downloader_from(body).list_dirs(specs)

    return jsonify(
        {
            "listings": [
                {"host": l.host, "paths": l.paths} for l in report.listings
            ],
            "failures": [
                {"host": x.host, "error": x.error, "remote_path": x.remote_path}
                for x in report.failures
            ],
        }
    )


@ftp_proxy_sknn_v3.post(URL_SIZE)
def size_dirs():
    # The sizing pass over HTTP: resolve each host's paths and SIZE them,
    # returning per-file byte counts only (no file bytes), so like the listing
    # route it carries none of the base64/RAM weight the download route does.
    denied = _unauthorized()
    if denied is not None:
        return denied

    body = request.get_json(force=True)
    specs = [_spec_from_wire(entry) for entry in body.get("specs", [])]
    report = _downloader_from(body).size_dirs(specs)

    return jsonify(
        {
            "files": [
                {"host": f.host, "remote_path": f.remote_path, "size": f.size}
                for f in report.files
            ],
            "failures": [
                {"host": x.host, "error": x.error, "remote_path": x.remote_path}
                for x in report.failures
            ],
        }
    )


@ftp_proxy_sknn_v3.post(URL_UPLOAD)
def upload():
    # The write direction: the client POSTs base64'd file bytes, this side does
    # the real STOR over FTP and returns a per-file ok/fail report (no bytes come
    # back). The request body carries the data, so ADR 0001's batch math bounds
    # RAM the same way — just on the inbound side.
    denied = _unauthorized()
    if denied is not None:
        return denied

    body = request.get_json(force=True)
    specs = [_upload_spec_from_wire(entry) for entry in body.get("specs", [])]
    report = _downloader_from(body).upload(specs)

    return jsonify(
        {
            "results": [
                {"host": r.host, "remote_path": r.remote_path}
                for r in report.results
            ],
            "failures": [
                {"host": x.host, "error": x.error, "remote_path": x.remote_path}
                for x in report.failures
            ],
        }
    )


def create_app() -> Flask:
    """Standalone app wrapping the blueprint — for running the proxy on its own
    and for tests. To attach to an existing app, register the blueprint
    directly instead."""
    app = Flask(__name__)
    app.register_blueprint(ftp_proxy_sknn_v3)
    return app


if __name__ == "__main__":
    port = int(os.getenv("FTP_PROXY_PORT", "8080"))
    create_app().run(host="0.0.0.0", port=port)
