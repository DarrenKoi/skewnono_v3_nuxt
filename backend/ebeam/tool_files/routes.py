import io
import logging
import threading
import time
import zipfile
from contextlib import contextmanager
from ftplib import all_errors, error_perm

from flask import Blueprint, Response, g, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.wsgi import wrap_file

from ftp_handler.core import (
    ListingTooLarge,
    TargetExists,
    TransferTimeout,
    TransferTooLarge,
    TransferUncertain,
)

from backend._auth.admin import is_admin_request
from backend._auth.errors import error_json
from backend.ebeam._tool_specs import VALID_TOOL_SLUGS
from backend.ebeam.tool_files.config import load_limits, write_enabled
from backend.ebeam.tool_files.access import ALLOWED_TEAMS, decide
from backend.ebeam.tool_files.contracts import Access, Entry, Listing, Verdict
from backend.ebeam.tool_files.data import open_client, probe, transport_supports_write
from backend.ebeam.tool_files.errors import ToolFilesError
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


@bp.after_request
def _no_store(response: Response) -> Response:
    # Listings and file bytes are access-controlled; no cache may replay them
    # to someone who has since left the allowed teams.
    response.headers["Cache-Control"] = "no-store"
    return response


def _verdict() -> Verdict:
    empno = getattr(g, "user_id", None)
    return decide(getattr(g, "identity_source", None), empno, lambda: probe(empno))


_REFUSALS: dict[str, tuple[int, str]] = {
    "none": (403, "forbidden"),
    "untrusted_identity": (403, "untrusted_identity"),
    "directory_unavailable": (503, "directory_unavailable"),
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
            400, "name_unencodable", f"name cannot be sent as {tool.encoding}: {exc}"
        ) from exc
    except error_perm as exc:
        # 550 means "missing" and "denied" alike, and a LIST line the parser
        # skipped proves nothing absent, so the two are one answer.
        raise ToolFilesError(404, "file_unavailable", str(exc)) from exc
    except all_errors as exc:
        raise ToolFilesError(503, "tool_unreachable", str(exc)) from exc
    finally:
        client.__exit__(None, None, None)


@bp.get("/tool-files/access")
def access():
    """Per person, not per tool: the verdict never reads which tool is asked."""
    can_write = write_enabled() and is_admin_request() and transport_supports_write()
    body: Access = {"verdict": _verdict(), "can_write": can_write, "teams": list(ALLOWED_TEAMS)}
    return jsonify(body)


_BROWSE_ROOT = "/"

# ponytail: per process, not fleet-wide (4 uWSGI processes = 4x the knob);
# a Redis semaphore if that is still too many at once.
_TRANSFERS = threading.BoundedSemaphore(load_limits().max_concurrent_transfers)


@contextmanager
def _transfer_slot():
    """Refuse at once rather than queue: a waiting download would hold the
    very request slot the cap exists to keep free."""
    if not _TRANSFERS.acquire(blocking=False):
        raise ToolFilesError(503, "transfers_busy", "another tool-file download is running")
    try:
        yield
    finally:
        _TRANSFERS.release()


@bp.get("/<tool_slug>/tool-files/list")
def list_files(tool_slug: str):
    _require_access()
    tool = _tool(tool_slug)
    limits = load_limits()
    # Browsing reaches "/" but opens at the login directory; writes stay
    # confined to the login directory.
    with _session(tool) as ftp:
        home = ftp.home()
        path = check_path(_BROWSE_ROOT, request.args.get("path") or home)
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
        "home": home,
        "path": path,
        "parent": parent_of(_BROWSE_ROOT, path),
        "crumbs": crumbs(_BROWSE_ROOT, path),
        "entries": entries,
        "max_bytes": limits.max_bytes,
        "max_batch_files": limits.max_batch_files,
    }
    return jsonify(body)


@bp.get("/<tool_slug>/tool-files/download")
def download(tool_slug: str):
    _require_access()
    tool = _tool(tool_slug)
    limits = load_limits()
    with _transfer_slot(), _session(tool) as ftp:
        path = check_path(_BROWSE_ROOT, request.args.get("path") or ftp.home())
        data = ftp.download(path, max_bytes=limits.max_bytes, deadline=limits.deadline)
    return _attachment(
        Response(data, mimetype="application/octet-stream"),
        readable_name(path.rsplit("/", 1)[-1]),
    )


def _attachment(response: Response, name: str) -> Response:
    response.headers["Content-Disposition"] = _content_disposition(name, kind="attachment")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.post("/<tool_slug>/tool-files/download-zip")
def download_zip(tool_slug: str):
    """Several files as one zip over one FTP session. ``max_bytes`` and the
    deadline are one budget for the whole zip, not one per file: a selection
    of files each under the cap must not add up to many times it."""
    _require_access()
    limits = load_limits()
    body = _json_body("fab, eqp_id, paths")
    paths = body.get("paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        raise ToolFilesError(400, "bad_request", "need a non-empty list of path strings")
    keys = [check_path(_BROWSE_ROOT, p) for p in dict.fromkeys(paths)]
    if len(keys) > limits.max_batch_files:
        raise ToolFilesError(
            413, "too_many_files", f"at most {limits.max_batch_files} files per zip"
        )
    names = [readable_name(key.rsplit("/", 1)[-1]) for key in keys]
    if len(set(names)) != len(names):
        raise ToolFilesError(400, "bad_request", "two of the files share a name")
    tool = _tool(tool_slug, body)
    buf = io.BytesIO()
    started = time.monotonic()
    budget = limits.max_bytes
    # Each file goes into the zip as it arrives, so the peak is the zip plus
    # one file, never every file at once. Level 1: logs still shrink well, at a
    # fraction of the default level's CPU on the request thread.
    archive = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=1)
    with _transfer_slot(), _session(tool) as ftp, archive:
        # The zip owns its budget, so it raises its own codes for both limits.
        def time_left() -> float:
            left = limits.deadline - (time.monotonic() - started)
            if left <= 0:
                raise ToolFilesError(
                    503, "tool_timeout", f"zip of {len(keys)} files ran past {limits.deadline}s"
                )
            return left

        for key, name in zip(keys, names, strict=True):
            try:
                data = ftp.download(key, max_bytes=budget, deadline=time_left())
            except TransferTooLarge as exc:
                raise ToolFilesError(
                    413, "batch_too_large", f"the files exceed {limits.max_bytes} bytes together"
                ) from exc
            budget -= len(data)
            archive.writestr(name, data)
            # Compressing counts too: the last file's has no next download to catch it.
            time_left()
    # Streamed from the buffer, not getvalue(): no second copy of a zip that
    # can near max_bytes.
    size = buf.tell()
    buf.seek(0)
    response = Response(
        wrap_file(request.environ, buf), mimetype="application/zip", direct_passthrough=True
    )
    response.content_length = size
    return _attachment(response, f"{tool.eqp_id}.zip")


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
    """Logs one audit line per mutation: the failure code, or ``ok``."""
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
    body = _json_body("fab, eqp_id, path")
    if not isinstance(body.get("path"), str):
        raise ToolFilesError(400, "bad_request", "need a JSON object with fab, eqp_id, path")
    tool = _tool(tool_slug, body)
    with _audited("delete", f"{tool.eqp_id}@{tool.fab_name}:{body['path']}"):
        with _session(tool) as ftp:
            path = check_path(ftp.home(), body["path"])
            ftp.remove(path)
    return jsonify({"deleted": path})


def _json_body(fields: str) -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ToolFilesError(400, "bad_request", f"need a JSON object with {fields}")
    return body


def _audit(action: str, key: str, result: str) -> None:
    logger.info(
        "tool_files %s actor=%s source=%s target=%s result=%s request_id=%s",
        action,
        g.user_id,
        getattr(g, "identity_source", None),
        key,
        result,
        getattr(g, "_activity_request_id", None),
    )
