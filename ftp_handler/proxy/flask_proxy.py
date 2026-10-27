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
         "host_timeout","passive","encoding",
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
    POST /mkdir_sknn_v3      request JSON (same tuning keys; mkdir -p per dir):
        {"specs":[{"host","dirs":[...]}]}
    200 response JSON:
        {"results":[{"host","remote_dir"}],
         "failures":[{"host","error","remote_path"}]}
    POST /delete_sknn_v3     request JSON (same tuning keys; DELE files, RMD empty dirs):
        {"specs":[{"host","files":[...],"dirs":[...]}]}
    200 response JSON (already-absent paths are results):
        {"results":[{"host","remote_path"}],
         "failures":[{"host","error","remote_path"}]}
    GET  /healthz_sknn_v3 -> {"status":"ok"}
    POST /list_details_sknn_v3, POST /fetch_sknn_v3, POST /write_sknn_v3
        single-server reads and writes for ``proxy_client.FtpClient`` (wire
        documented there): one fresh FTP connection per request.

Auth: if env FTP_PROXY_TOKEN is set, requests must carry
``Authorization: Bearer <token>`` or get 401. Always serve behind HTTPS in
production — file bytes AND the equipment FTP credentials cross this
connection. Each wire spec normally carries the ``user``/``password`` the
client was built with (since 2026-08-28: the proxy cannot otherwise honour the
account its caller chose, and one fleet is not one account). The proxy host's
``FTP_PROXY_FTP_USER`` / ``FTP_PROXY_FTP_PASSWORD`` are the fallback for a spec
that names neither — an older client, or a caller that wants the host default.

Standalone run (without an existing app):
    pip install flask
    set FTP_PROXY_FTP_USER=ftpuser
    set FTP_PROXY_FTP_PASSWORD=ftppass
    set FTP_PROXY_TOKEN=secret    # PowerShell: $env:FTP_PROXY_TOKEN="secret"
    python flask_proxy.py                           # serves 0.0.0.0:8080
"""

import base64
import hmac
import os
from pathlib import Path

from flask import Blueprint, Flask, Response, jsonify, request

# Import the real downloader, whether this module is run as a package member or
# copied out flat beside fleet_downloader.py and run as a script.
try:
    from ..direct_downloader.fleet_downloader import (
        DeleteSpec,
        FtpFleetDownloader,
        HostSpec,
        ListDir,
        MkdirSpec,
        UploadFile,
        UploadSpec,
    )
except ImportError:  # copied beside fleet_downloader.py and imported bare
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fleet_downloader import (
        DeleteSpec,
        FtpFleetDownloader,
        HostSpec,
        ListDir,
        MkdirSpec,
        UploadFile,
        UploadSpec,
    )

# Suffixed to avoid collisions with routes already mounted on the host app.
# Keep in sync with the paths proxy_downloader.py POSTs to.
URL_DOWNLOAD = "/download_sknn_v3"
URL_LIST = "/list_dirs_sknn_v3"
URL_SIZE = "/size_dirs_sknn_v3"
URL_UPLOAD = "/upload_sknn_v3"
URL_MKDIR = "/mkdir_sknn_v3"
URL_DELETE = "/delete_sknn_v3"
URL_HEALTH = "/healthz_sknn_v3"
# Single-server reads for ``proxy_client.FtpClient``; wire documented there.
URL_LIST_DETAILS = "/list_details_sknn_v3"
URL_FETCH = "/fetch_sknn_v3"
URL_WRITE = "/write_sknn_v3"
ERROR_STATUS = 422

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


def _mkdir_spec_from_wire(entry: dict) -> MkdirSpec:
    return MkdirSpec(
        host=entry["host"],
        dirs=list(entry.get("dirs", [])),
        user=entry.get("user"),
        password=entry.get("password"),
    )


def _delete_spec_from_wire(entry: dict) -> DeleteSpec:
    return DeleteSpec(
        host=entry["host"],
        files=list(entry.get("files", [])),
        dirs=list(entry.get("dirs", [])),
        user=entry.get("user"),
        password=entry.get("password"),
    )


def _unauthorized():
    """Return a 401 response if the request fails the bearer-token check, else
    ``None``. Token is read per request so it can be configured independently of
    when the host app (and this blueprint) were imported."""
    token = os.getenv("FTP_PROXY_TOKEN")
    if token is not None and not hmac.compare_digest(
        request.headers.get("Authorization", ""), f"Bearer {token}"
    ):
        return jsonify({"error": "unauthorized"}), 401
    return None


def _downloader_from(body: dict) -> FtpFleetDownloader:
    """Build the FtpFleetDownloader from the request body's tuning.

    Credentials come from the spec (see ``_spec_from_wire``) -- since
    2026-08-28 a client sends the account it wants for each host, which is the
    only way one request can span two accounts. The values built in here are
    the FALLBACK for a spec that names none, read from the proxy host's
    ``FTP_PROXY_FTP_USER`` / ``FTP_PROXY_FTP_PASSWORD`` if they are set at all.

    The remaining tuning comes from the client so proxy-side behavior matches
    the direct adapter. host_timeout default 45s stays under the host app's
    harakiri=60 so the downloader's own backstop fires before uWSGI kills the
    request. See ADR 0001.
    """
    return FtpFleetDownloader(
        # ``getenv``, not ``environ[...]``: since 2026-08-28 every client sends
        # the account it wants per spec, so this pair is the fallback for a spec
        # that names none — not a boot requirement. A proxy host that has
        # retired the variables must serve those clients, not 500 at them.
        user=os.getenv("FTP_PROXY_FTP_USER", ""),
        password=os.getenv("FTP_PROXY_FTP_PASSWORD", ""),
        port=body.get("port", 21),
        max_concurrency=body.get("max_concurrency", 48),
        connect_timeout=body.get("connect_timeout", 8.0),
        host_timeout=body.get("host_timeout", 45.0),
        passive=body.get("passive", True),
        # Absent from an older client's body -> utf-8, ftplib's own default.
        encoding=body.get("encoding", "utf-8"),
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
                {
                    "host": f.host,
                    "remote_path": f.remote_path,
                    "size": f.size,
                    # UTC ISO-8601, or null when the server has no MDTM. Absent
                    # from an older proxy's reply, which the client reads as None.
                    "modified": f.modified.isoformat() if f.modified else None,
                }
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


@ftp_proxy_sknn_v3.post(URL_MKDIR)
def mkdir():
    denied = _unauthorized()
    if denied is not None:
        return denied

    body = request.get_json(force=True)
    specs = [_mkdir_spec_from_wire(entry) for entry in body.get("specs", [])]
    report = _downloader_from(body).mkdir(specs)

    return jsonify(
        {
            "results": [
                {"host": r.host, "remote_dir": r.remote_dir} for r in report.results
            ],
            "failures": [
                {"host": x.host, "error": x.error, "remote_path": x.remote_path}
                for x in report.failures
            ],
        }
    )


@ftp_proxy_sknn_v3.post(URL_DELETE)
def delete():
    denied = _unauthorized()
    if denied is not None:
        return denied

    body = request.get_json(force=True)
    specs = [_delete_spec_from_wire(entry) for entry in body.get("specs", [])]
    report = _downloader_from(body).delete(specs)

    return jsonify(
        {
            "results": [
                {"host": r.host, "remote_path": r.remote_path} for r in report.results
            ],
            "failures": [
                {"host": x.host, "error": x.error, "remote_path": x.remote_path}
                for x in report.failures
            ],
        }
    )


class _BadRequest(Exception):
    pass


def _read_body() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("host"), str):
        raise _BadRequest("need a JSON object with a host")
    return body


def _single_client(body: dict):
    """A ``core.FtpClient`` from the request envelope. Imported here, not at the
    top, so the five fleet routes keep working from a flat copy-out bundle that
    has no ``ftp_handler`` package beside it."""
    from ftp_handler.core.client import FtpClient

    return FtpClient(
        host=body["host"],
        # Same fallback as _downloader_from: the envelope names the account;
        # the proxy host's pair covers a request that names none.
        user=body.get("user", os.getenv("FTP_PROXY_FTP_USER", "")),
        password=body.get("password", os.getenv("FTP_PROXY_FTP_PASSWORD", "")),
        port=body.get("port", 21),
        timeout=body.get("timeout", 8.0),
        passive=body.get("passive", True),
        encoding=body.get("encoding", "utf-8"),
    )


def _single_op(op):
    """Run ``op(ftp, body)`` on a fresh connection; map failures to ``{code, error}``.

    Connect/login failures are ``unreachable`` whatever ftplib raised (a 530 is
    an ``error_perm`` too, and must not read as a missing file). A name, banner
    or PWD reply the server charset cannot decode is ``encoding`` wherever it
    happens: ``UnicodeError`` is neither in ``ftplib.all_errors`` nor a bad
    request, though it subclasses ``ValueError``, so it is caught first.
    """
    from ftplib import all_errors, error_perm

    from ftp_handler.core.client import (
        ListingTooLarge,
        TargetExists,
        TransferTimeout,
        TransferTooLarge,
        TransferUncertain,
    )

    def fail(code: str, exc: BaseException):
        body = {"code": code, "error": str(exc)}
        # A failed put names the temp it could not clean up; the caller needs
        # it to tidy or retry, as it would from the direct client.
        if getattr(exc, "temp_path", None):
            body["temp_path"] = exc.temp_path
        return jsonify(body), ERROR_STATUS

    try:
        body = _read_body()
        client = _single_client(body)
    except (_BadRequest, TypeError, ValueError) as exc:
        return fail("bad_request", exc)
    try:
        ftp = client.__enter__()
    except UnicodeError as exc:
        return fail("encoding", exc)
    except all_errors as exc:
        return fail("unreachable", exc)
    try:
        return op(ftp, body)
    except UnicodeError as exc:
        return fail("encoding", exc)
    except (_BadRequest, TypeError, ValueError) as exc:
        return fail("bad_request", exc)
    except TransferTooLarge as exc:
        return fail("too_large", exc)
    except ListingTooLarge as exc:
        return fail("listing_too_large", exc)
    except TransferTimeout as exc:
        return fail("timeout", exc)
    except TargetExists as exc:
        return fail("exists", exc)
    except TransferUncertain as exc:
        return fail("uncertain", exc)
    except error_perm as exc:
        return fail("unavailable", exc)
    except all_errors as exc:
        return fail("unreachable", exc)
    finally:
        client.__exit__(None, None, None)


def _list_details(ftp, body: dict):
    from datetime import timedelta, timezone

    home = ftp.home()
    if body.get("home_only"):
        # PWD only: home() must not pay for an uncapped LIST of the home dir.
        return jsonify({"home": home, "entries": []})
    remote_dir = body.get("remote_dir")
    kwargs = {}
    if body.get("tz_offset_s") is not None:
        kwargs["tz"] = timezone(timedelta(seconds=body["tz_offset_s"]))
    infos = ftp.list_details(
        home if remote_dir is None else remote_dir,
        body.get("pattern"),
        max_entries=body.get("max_entries"),
        max_raw_bytes=body.get("max_raw_bytes"),
        deadline=body.get("deadline_s"),
        **kwargs,
    )
    return jsonify(
        {
            "home": home,
            "entries": [
                {
                    "name": i.name,
                    "path": i.path,
                    "is_dir": i.is_dir,
                    "size": i.size,
                    "modified": i.modified.isoformat() if i.modified else None,
                    "is_link": i.is_link,
                    "raw": i.raw,
                }
                for i in infos
            ],
        }
    )


@ftp_proxy_sknn_v3.post(URL_LIST_DETAILS)
def list_details():
    denied = _unauthorized()
    if denied is not None:
        return denied
    return _single_op(_list_details)


def _fetch(ftp, body: dict):
    remote_path = body.get("remote_path")
    if not isinstance(remote_path, str) or not remote_path:
        raise _BadRequest("need a remote_path")
    # core.download checks max_bytes and the deadline per FTP chunk; the bytes
    # are only sent once the whole file is in, so a failure can still be JSON.
    data = ftp.download(
        remote_path, max_bytes=body.get("max_bytes"), deadline=body.get("deadline_s")
    )
    return Response(data, mimetype="application/octet-stream")


@ftp_proxy_sknn_v3.post(URL_FETCH)
def fetch():
    denied = _unauthorized()
    if denied is not None:
        return denied
    return _single_op(_fetch)


def _write(ftp, body: dict):
    remote_path = body.get("remote_path")
    if not isinstance(remote_path, str) or not remote_path:
        raise _BadRequest("need a remote_path")
    op = body.get("op")
    if op in ("upload", "put"):
        # validate=True: a malformed payload is a bad request, never a file
        # silently stored with the junk characters dropped.
        data = base64.b64decode(body.get("data_b64"), validate=True)
        if op == "upload":
            ftp.upload(remote_path, data)
        else:
            ftp.put(remote_path, data, deadline=body.get("deadline_s"))
    elif op in ("remove", "mkdir", "rmdir"):
        getattr(ftp, op)(remote_path)
    else:
        raise _BadRequest(f"unknown write op {op!r}")
    return jsonify({"ok": True})


@ftp_proxy_sknn_v3.post(URL_WRITE)
def write():
    denied = _unauthorized()
    if denied is not None:
        return denied
    return _single_op(_write)


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
