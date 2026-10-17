import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from ftplib import all_errors, error_perm

from flask import Blueprint, Response, g, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from ftp_handler.core import (
    ListingTooLarge,
    TargetExists,
    TransferTimeout,
    TransferTooLarge,
    TransferUncertain,
)

from backend._auth.admin import is_admin_request, require_admin
from backend._auth.errors import error_json
from backend.ebeam._tool_specs import VALID_TOOL_SLUGS
from backend.ebeam.tool_files.config import load_limits, write_enabled
from backend.ebeam.tool_files.access import decide, emp_key, norm_empno, team_key
from backend.ebeam.tool_files.contracts import (
    Access,
    Entry,
    Grant,
    GrantRow,
    Listing,
    Request,
    RequestRow,
    Verdict,
)
from backend.ebeam.tool_files.data import (
    approve_request,
    approve_team,
    delete_grant,
    open_client,
    probe,
    put_grant,
    put_request,
    read_grants,
    read_requests,
    reject_request,
    teams,
    transport_supports_write,
)
from backend.ebeam.tool_files.errors import (
    DirectoryUnavailable,
    RequestChanged,
    StoreUnavailable,
    ToolFilesError,
)
from backend.ebeam.tool_files.paths import check_path, crumbs, parent_of, readable_name
from backend.ebeam.tool_files.resolve import Tool, resolve_tool
from backend.msr_image.config import load_config
from backend.msr_image.routes import _content_disposition
from backend.sem_list.data import get_sem_list

bp = Blueprint("tool_files", __name__)
logger = logging.getLogger("skewnono.tool_files")


@bp.errorhandler(ToolFilesError)
def _tool_files_error(err: ToolFilesError):
    return error_json(err.code, err.message, err.status)


@bp.errorhandler(RequestEntityTooLarge)
def _upload_too_large(_err: RequestEntityTooLarge):
    return error_json("too_large", "upload exceeds the size cap", 413)


@bp.errorhandler(StoreUnavailable)
def _store_unavailable(err: StoreUnavailable):
    return error_json("store_unavailable", str(err), 503)


@bp.errorhandler(DirectoryUnavailable)
def _directory_unavailable(err: DirectoryUnavailable):
    return error_json("directory_unavailable", str(err), 503)


@bp.errorhandler(RequestChanged)
def _request_changed(_err: RequestChanged):
    return error_json(
        "request_changed", "the request was replaced or withdrawn; reload and check again", 409
    )


@bp.after_request
def _no_store(response: Response) -> Response:
    # Listings and file bytes are access-controlled; no cache may replay them
    # after a grant is revoked.
    response.headers["Cache-Control"] = "no-store"
    return response


def _or_none(read):
    try:
        return read()
    except StoreUnavailable:
        return None


def _judge() -> tuple[Verdict, dict]:
    """The verdict, plus whatever ``decide`` read on the way ("probe",
    "requests"), so a caller reuses it instead of asking twice."""
    empno = getattr(g, "user_id", None)
    seen: dict = {}

    def remember(name, read):
        def call():
            seen[name] = read()
            return seen[name]

        return call

    verdict = decide(
        getattr(g, "identity_source", None),
        empno,
        lambda: _or_none(read_grants),
        remember("probe", lambda: probe(empno)),
        remember("requests", lambda: _or_none(read_requests)),
    )
    return verdict, seen


def _verdict() -> Verdict:
    return _judge()[0]


_REFUSALS: dict[str, tuple[int, str]] = {
    "none": (403, "forbidden"),
    "pending": (403, "forbidden"),
    "rejected": (403, "forbidden"),
    "untrusted_identity": (403, "untrusted_identity"),
    "directory_unavailable": (503, "directory_unavailable"),
    "store_unavailable": (503, "store_unavailable"),
}


def _require_access() -> None:
    verdict = _verdict()
    if verdict != "granted":
        status, code = _REFUSALS[verdict]
        raise ToolFilesError(status, code, f"tool file access refused: {verdict}")


def _tool(tool_slug: str, source=None) -> Tool:
    source = request.args if source is None else source
    fab, eqp_id = source.get("fab", ""), source.get("eqp_id", "")
    if not isinstance(fab, str) or not isinstance(eqp_id, str):
        raise ToolFilesError(400, "bad_request", "fab and eqp_id must be strings")
    if tool_slug not in VALID_TOOL_SLUGS or not fab or not eqp_id:
        raise ToolFilesError(400, "bad_request", "need a valid tool_slug, fab and eqp_id")
    return resolve_tool(get_sem_list(), tool_slug, fab, eqp_id, load_config())


def _encoding_error(tool: Tool, exc: UnicodeDecodeError) -> ToolFilesError:
    # ftplib decodes replies and LIST strictly, and UnicodeDecodeError is not
    # in all_errors: unmapped it is a 500 that names no cause.
    return ToolFilesError(
        502,
        "tool_encoding",
        f"{tool.eqp_id} sent names that are not {tool.encoding}; "
        f"set SKEWNONO_TOOL_FTP_ENCODING (latin-1 at the office): {exc}",
    )


@contextmanager
def _session(tool: Tool):
    client = open_client(tool)
    try:
        ftp = client.__enter__()
    except UnicodeDecodeError as exc:
        raise _encoding_error(tool, exc) from exc
    except all_errors as exc:
        raise ToolFilesError(
            503, "tool_unreachable", f"cannot log in to {tool.eqp_id}: {exc}"
        ) from exc
    try:
        yield ftp
    except TransferTooLarge as exc:
        raise ToolFilesError(413, "too_large", str(exc)) from exc
    except ListingTooLarge as exc:
        raise ToolFilesError(413, "listing_too_large", str(exc)) from exc
    except TransferTimeout as exc:
        raise ToolFilesError(503, "tool_timeout", str(exc)) from exc
    except TargetExists as exc:
        raise ToolFilesError(409, "file_exists", f"{exc} already exists") from exc
    except TransferUncertain as exc:
        raise ToolFilesError(
            503, "transfer_uncertain", "the tool may or may not have the file; list again"
        ) from exc
    except UnicodeDecodeError as exc:
        raise _encoding_error(tool, exc) from exc
    except UnicodeEncodeError as exc:
        # An upload name the tool's encoding cannot carry (Korean under latin-1).
        raise ToolFilesError(
            400, "bad_path", f"name cannot be sent as {tool.encoding}: {exc}"
        ) from exc
    except error_perm as exc:
        # 550 means "missing" and "denied" alike, and a LIST line the parser
        # skipped proves nothing absent, so the two are one answer.
        raise ToolFilesError(404, "file_unavailable", str(exc)) from exc
    except all_errors as exc:
        raise ToolFilesError(503, "tool_unreachable", str(exc)) from exc
    finally:
        client.__exit__(None, None, None)


@bp.get("/<tool_slug>/tool-files/access")
def access(tool_slug: str):
    can_write = write_enabled() and is_admin_request() and transport_supports_write()
    verdict, seen = _judge()
    body: Access = {"verdict": verdict, "can_write": can_write}
    if verdict in ("pending", "rejected"):
        body["request"] = seen["requests"][norm_empno(g.user_id)]
    return jsonify(body)


_MAX_REASON = 200


@bp.post("/tool-files/requests")
def request_access():
    """Only ``reason`` is read from the body: the empno is the caller's own
    identity and dept_nm comes from the directory, whatever the client sent."""
    verdict, seen = _judge()
    if verdict == "untrusted_identity":
        raise ToolFilesError(403, "untrusted_identity", "this identity source cannot request access")
    body = request.get_json(silent=True)
    reason = body.get("reason") if isinstance(body, dict) else None
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > _MAX_REASON:
        raise ToolFilesError(400, "bad_request", f"need a reason of 1-{_MAX_REASON} characters")
    if verdict == "granted":
        return jsonify({"verdict": "granted"})
    if verdict in ("directory_unavailable", "store_unavailable"):
        status, code = _REFUSALS[verdict]
        raise ToolFilesError(status, code, f"cannot take a request now: {verdict}")
    empno = norm_empno(g.user_id)
    member = seen["probe"].member
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    record: Request = {
        "request_id": uuid.uuid4().hex,
        "reason": reason.strip(),
        "dept_nm": member["dept_nm"] if member else None,
        "requested_at": stamp,
        "status": "pending",
    }
    try:
        put_request(empno, record)
    except StoreUnavailable:
        _audit("request", empno, "store_unavailable", record["request_id"])
        raise
    _audit("request", empno, "ok", record["request_id"])
    return jsonify({"verdict": "pending", "request": record}), 201


@bp.get("/<tool_slug>/tool-files/list")
def list_files(tool_slug: str):
    _require_access()
    tool = _tool(tool_slug)
    limits = load_limits()
    with _session(tool) as ftp:
        root = ftp.home()
        path = check_path(root, request.args.get("path"))
        infos = ftp.list_details(
            path,
            max_entries=limits.max_entries,
            max_raw_bytes=limits.max_list_bytes,
            deadline=limits.deadline,
        )
    # Links are hidden: LIST drops their target, so nothing here can say
    # whether one leads outside the root.
    entries: list[Entry] = [
        {
            "name": readable_name(info.name),
            "path": info.path,
            "is_dir": info.is_dir,
            "size": info.size,
            "modified": info.modified.isoformat() if info.modified else None,
        }
        for info in infos
        if not info.is_link
    ]
    body: Listing = {
        "root": root,
        "path": path,
        "parent": parent_of(root, path),
        "crumbs": crumbs(root, path),
        "entries": entries,
        "max_bytes": limits.max_bytes,
    }
    return jsonify(body)


@bp.get("/<tool_slug>/tool-files/download")
def download(tool_slug: str):
    _require_access()
    tool = _tool(tool_slug)
    limits = load_limits()
    with _session(tool) as ftp:
        path = check_path(ftp.home(), request.args.get("path"))
        data = ftp.download(path, max_bytes=limits.max_bytes, deadline=limits.deadline)
    response = Response(data, mimetype="application/octet-stream")
    response.headers["Content-Disposition"] = _content_disposition(
        readable_name(path.rsplit("/", 1)[-1]), kind="attachment"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _require_write() -> None:
    """Called before anything reads the body or opens FTP."""
    if not write_enabled():
        raise ToolFilesError(403, "write_disabled", "tool file writes are switched off")
    if not is_admin_request():
        raise ToolFilesError(403, "forbidden", "only an admin may write tool files")
    if not transport_supports_write():
        raise ToolFilesError(501, "write_not_supported", "this transport cannot write")
    _require_access()


@contextmanager
def _audited(action: str, target: str):
    try:
        yield
    except ToolFilesError as exc:
        _audit(action, target, exc.code)
        raise
    _audit(action, target, "ok")


@bp.post("/<tool_slug>/tool-files/upload")
def upload(tool_slug: str):
    _require_write()
    limits = load_limits()
    cap = limits.max_upload_bytes
    if (request.content_length or 0) > cap:
        raise ToolFilesError(413, "too_large", f"upload exceeds {cap} bytes")
    # The bytes actually read are counted too: a body that names no
    # Content-Length (chunked) is cut off at the cap while it is parsed.
    request.max_content_length = cap
    tool = _tool(tool_slug, request.form)
    files, folder = request.files.getlist("file"), request.form.get("dir", "")
    if len(files) != 1 or len(request.files) != 1:
        raise ToolFilesError(400, "bad_request", "need exactly one file")
    data = files[0].read()
    name = (files[0].filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    with _audited("upload", f"{tool.eqp_id}@{tool.fab_name}:{folder}/{name}"):
        with _session(tool) as ftp:
            root = ftp.home()
            folder = check_path(root, folder)
            path = check_path(root, f"{folder.rstrip('/')}/{name}")
            ftp.put(path, data, deadline=limits.deadline)
    return jsonify({"path": path}), 201


@bp.post("/<tool_slug>/tool-files/delete")
def delete(tool_slug: str):
    _require_write()
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("path"), str):
        raise ToolFilesError(400, "bad_request", "need a JSON object with fab, eqp_id, path")
    tool = _tool(tool_slug, body)
    with _audited("delete", f"{tool.eqp_id}@{tool.fab_name}:{body['path']}"):
        with _session(tool) as ftp:
            path = check_path(ftp.home(), body["path"])
            ftp.remove(path)
    return jsonify({"deleted": path})


def _grant_key() -> str:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ToolFilesError(400, "bad_request", "need a JSON object with kind and value")
    kind, value = body.get("kind"), body.get("value")
    if kind not in ("team", "emp") or not isinstance(value, str) or not value.strip():
        raise ToolFilesError(400, "bad_request", "need kind 'team' or 'emp' and a value")
    return team_key(value) if kind == "team" else emp_key(value)


def _audit(action: str, key: str, result: object, access_request_id: str | None = None) -> None:
    logger.info(
        "tool_files %s actor=%s source=%s target=%s result=%s request_id=%s"
        " access_request_id=%s",
        action,
        g.user_id,
        getattr(g, "identity_source", None),
        key,
        result,
        getattr(g, "_activity_request_id", None),
        access_request_id,
    )


def _grant_row(key: str, grant: Grant) -> GrantRow:
    kind, value = key.split(":", 1)
    dept_nm = None
    if kind == "emp":
        found = probe(value)
        dept_nm = found.member["dept_nm"] if found.member else None
    return {"kind": kind, "value": value, "dept_nm": dept_nm, **grant}


def _request_row(empno: str, stored: Request) -> RequestRow:
    found = probe(empno)
    emp_nm = found.member["emp_nm"] if found.member else None
    return {"empno": empno, "emp_nm": emp_nm, **stored}


@bp.get("/admin/tool-files")
@require_admin
def admin_overview():
    grants, requests = read_grants(), read_requests()
    return jsonify(
        {
            "grants": [_grant_row(key, grants[key]) for key in sorted(grants)],
            "requests": [
                _request_row(empno, requests[empno])
                for empno in sorted(requests, key=lambda e: requests[e].get("requested_at", ""))
            ],
        }
    )


@bp.get("/admin/tool-files/teams")
@require_admin
def admin_teams():
    return jsonify(teams())


def _new_grant() -> Grant:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"granted_at": stamp, "granted_by": g.user_id}


def _string(body: dict, name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ToolFilesError(400, "bad_request", f"need a non-empty string {name}")
    return value.strip()


def _decision_body() -> tuple[str, str]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ToolFilesError(400, "bad_request", "need a JSON object with empno and request_id")
    return norm_empno(_string(body, "empno")), _string(body, "request_id")


@contextmanager
def _audited_decision(action: str, target: str, access_request_id: str | None):
    try:
        yield
    except RequestChanged:
        _audit(action, target, "request_changed", access_request_id)
        raise
    except StoreUnavailable:
        _audit(action, target, "store_unavailable", access_request_id)
        raise
    _audit(action, target, "ok", access_request_id)


@bp.post("/admin/tool-files/requests/approve")
@require_admin
def admin_approve():
    empno, request_id = _decision_body()
    with _audited_decision("approve", empno, request_id):
        approve_request(empno, request_id, _new_grant())
    return jsonify({"approved": empno})


@bp.post("/admin/tool-files/requests/reject")
@require_admin
def admin_reject():
    empno, request_id = _decision_body()
    with _audited_decision("reject", empno, request_id):
        reject_request(empno, request_id)
    return jsonify({"rejected": empno})


@bp.post("/admin/tool-files/teams/approve")
@require_admin
def admin_approve_team():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ToolFilesError(400, "bad_request", "need a JSON object with dept_nm")
    dept_nm = _string(body, "dept_nm")
    key = team_key(dept_nm)
    try:
        grant, cleared = approve_team(dept_nm, _new_grant())
    except StoreUnavailable:
        _audit("team_approve", key, "store_unavailable")
        raise
    _audit("team_approve", key, f"ok cleared={','.join(cleared) or '-'}")
    return jsonify({**_grant_row(key, grant), "cleared": cleared}), 201


@bp.post("/admin/tool-files/grants")
@require_admin
def admin_grant():
    key = _grant_key()
    try:
        grant = put_grant(key, _new_grant())
    except StoreUnavailable:
        _audit("grant", key, "store_unavailable")
        raise
    _audit("grant", key, "ok")
    return jsonify(_grant_row(key, grant)), 201


@bp.post("/admin/tool-files/grants/revoke")
@require_admin
def admin_revoke():
    key = _grant_key()
    try:
        revoked = delete_grant(key)
    except StoreUnavailable:
        _audit("revoke", key, "store_unavailable")
        raise
    _audit("revoke", key, "ok" if revoked else "absent")
    return jsonify({"revoked": revoked})
