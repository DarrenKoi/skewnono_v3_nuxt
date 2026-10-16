import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from ftplib import all_errors, error_perm

from flask import Blueprint, Response, g, jsonify, request

from ftp_handler.core import ListingTooLarge, TransferTimeout, TransferTooLarge

from backend._auth.admin import require_admin
from backend._auth.errors import error_json
from backend.ebeam._tool_specs import VALID_TOOL_SLUGS
from backend.ebeam.tool_files.config import load_limits
from backend.ebeam.tool_files.access import decide, emp_key, team_key
from backend.ebeam.tool_files.contracts import (
    Access,
    Entry,
    Grant,
    GrantRow,
    Listing,
    Verdict,
)
from backend.ebeam.tool_files.data import (
    delete_grant,
    open_client,
    probe,
    put_grant,
    read_grants,
    teams,
)
from backend.ebeam.tool_files.errors import (
    DirectoryUnavailable,
    StoreUnavailable,
    ToolFilesError,
)
from backend.ebeam.tool_files.paths import check_path, crumbs, parent_of
from backend.ebeam.tool_files.resolve import Tool, resolve_tool
from backend.msr_image.config import load_config
from backend.msr_image.routes import _content_disposition
from backend.sem_list.data import get_sem_list

bp = Blueprint("tool_files", __name__)
logger = logging.getLogger("skewnono.tool_files")


@bp.errorhandler(ToolFilesError)
def _tool_files_error(err: ToolFilesError):
    return error_json(err.code, err.message, err.status)


@bp.errorhandler(StoreUnavailable)
def _store_unavailable(err: StoreUnavailable):
    return error_json("store_unavailable", str(err), 503)


@bp.errorhandler(DirectoryUnavailable)
def _directory_unavailable(err: DirectoryUnavailable):
    return error_json("directory_unavailable", str(err), 503)


@bp.after_request
def _no_store(response: Response) -> Response:
    # Listings and file bytes are access-controlled; no cache may replay them
    # after a grant is revoked.
    response.headers["Cache-Control"] = "no-store"
    return response


def _stored_grants() -> dict[str, Grant] | None:
    try:
        return read_grants()
    except StoreUnavailable:
        return None


def _verdict() -> Verdict:
    empno = getattr(g, "user_id", None)
    return decide(
        getattr(g, "identity_source", None),
        empno,
        _stored_grants,
        lambda: probe(empno),
    )


_REFUSALS: dict[str, tuple[int, str]] = {
    "none": (403, "forbidden"),
    "untrusted_identity": (403, "untrusted_identity"),
    "directory_unavailable": (503, "directory_unavailable"),
    "store_unavailable": (503, "store_unavailable"),
}


def _require_access() -> None:
    verdict = _verdict()
    if verdict != "granted":
        status, code = _REFUSALS[verdict]
        raise ToolFilesError(status, code, f"tool file access refused: {verdict}")


def _tool(tool_slug: str) -> Tool:
    fab = request.args.get("fab", "")
    eqp_id = request.args.get("eqp_id", "")
    if tool_slug not in VALID_TOOL_SLUGS or not fab or not eqp_id:
        raise ToolFilesError(400, "bad_request", "need a valid tool_slug, fab and eqp_id")
    return resolve_tool(get_sem_list(), tool_slug, fab, eqp_id, load_config())


@contextmanager
def _session(tool: Tool):
    client = open_client(tool)
    try:
        ftp = client.__enter__()
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
    body: Access = {"verdict": _verdict(), "can_write": False}
    return jsonify(body)


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
            "name": info.name,
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
        path.rsplit("/", 1)[-1], kind="attachment"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _grant_key() -> str:
    body = request.get_json(silent=True) or {}
    kind, value = body.get("kind"), body.get("value")
    if kind not in ("team", "emp") or not isinstance(value, str) or not value.strip():
        raise ToolFilesError(400, "bad_request", "need kind 'team' or 'emp' and a value")
    return team_key(value) if kind == "team" else emp_key(value)


def _audit(action: str, key: str, result: object) -> None:
    logger.info(
        "tool_files %s actor=%s target=%s result=%s request_id=%s",
        action,
        g.user_id,
        key,
        result,
        getattr(g, "_activity_request_id", None),
    )


def _grant_row(key: str, grant: Grant) -> GrantRow:
    kind, value = key.split(":", 1)
    dept_nm = None
    if kind == "emp":
        found = probe(value)
        dept_nm = found.member["dept_nm"] if found.member else None
    return {"kind": kind, "value": value, "dept_nm": dept_nm, **grant}


@bp.get("/admin/tool-files")
@require_admin
def admin_overview():
    grants = read_grants()
    return jsonify({"grants": [_grant_row(key, grants[key]) for key in sorted(grants)]})


@bp.get("/admin/tool-files/teams")
@require_admin
def admin_teams():
    return jsonify(teams())


@bp.post("/admin/tool-files/grants")
@require_admin
def admin_grant():
    key = _grant_key()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        grant = put_grant(key, {"granted_at": stamp, "granted_by": g.user_id})
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
