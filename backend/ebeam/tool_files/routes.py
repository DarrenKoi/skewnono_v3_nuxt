from contextlib import contextmanager
from ftplib import all_errors, error_perm

from flask import Blueprint, Response, jsonify, request

from ftp_handler.core import ListingTooLarge, TransferTimeout, TransferTooLarge

from backend._auth.admin import is_admin_request
from backend._auth.errors import error_json
from backend.ebeam._tool_specs import VALID_TOOL_SLUGS
from backend.ebeam.tool_files.config import load_limits
from backend.ebeam.tool_files.contracts import Access, Entry, Listing
from backend.ebeam.tool_files.data import open_client
from backend.ebeam.tool_files.errors import ToolFilesError
from backend.ebeam.tool_files.paths import check_path, crumbs, parent_of
from backend.ebeam.tool_files.resolve import Tool, resolve_tool
from backend.msr_image.config import load_config
from backend.msr_image.routes import _content_disposition
from backend.sem_list.data import get_sem_list

bp = Blueprint("tool_files", __name__)


@bp.errorhandler(ToolFilesError)
def _tool_files_error(err: ToolFilesError):
    return error_json(err.code, err.message, err.status)


@bp.after_request
def _no_store(response: Response) -> Response:
    # Listings and file bytes are access-controlled; no cache may replay them
    # after a grant is revoked.
    response.headers["Cache-Control"] = "no-store"
    return response


def _require_access() -> None:
    if not is_admin_request():
        raise ToolFilesError(403, "forbidden", "tool file access has not been granted")


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
    granted = is_admin_request()
    body: Access = {"verdict": "granted" if granted else "none", "can_write": False}
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
