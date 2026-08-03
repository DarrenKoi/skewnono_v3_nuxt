"""msr_image blueprint. Phase-agnostic: assembles locators, delegates bytes to
the data seam, caches, and relays. Office knowledge is only in providers/office."""

import threading
from urllib.parse import quote

from flask import Blueprint, Response, current_app, jsonify, request

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import ImageListResponse, ImageLocator
from back_dev_home.msr_image.errors import MsrImageError
from back_dev_home.msr_image.jobs import make_registry
from back_dev_home.msr_image.paths import validate_locator, validate_segment, validate_tool_ip

bp = Blueprint("msr_image", __name__)


def _error(exc: MsrImageError):
    return jsonify({"error": str(exc) or exc.code, "code": exc.code}), exc.status


def _get_cache(cfg):
    """One ImageCache per (app, provider). The gallery fans out many image GETs;
    rebuilding the backend — and, office-side, a fresh MinIO SDK client with its
    own connection pool — on every request is wasted work. Cached on
    ``current_app.extensions`` so it's per-app-instance (test-isolated)."""
    provider = data.provider_name()
    key = f"msr_image_cache::{provider}"
    ext = current_app.extensions
    cache = ext.get(key)
    if cache is None:
        cache = make_cache(cfg, provider)
        ext[key] = cache
    return cache


def _require(*names: str) -> dict[str, str] | None:
    out = {}
    for n in names:
        v = (request.args.get(n) or "").strip()
        if not v:
            return None
        out[n] = v
    return out


@bp.get("/msr-images")
def list_images_route():
    args = _require("eqp_ip", "class_name", "msr")
    if args is None:
        return jsonify({"error": "eqp_ip, class_name, msr are required"}), 400
    cfg = load_config()
    try:
        validate_tool_ip(args["eqp_ip"], cfg.allowed_subnets)
        validate_segment(args["class_name"], "class_name")
        validate_segment(args["msr"], "msr")
        names = data.list_images(args["eqp_ip"], args["class_name"], args["msr"])
    except MsrImageError as exc:
        return _error(exc)
    body: ImageListResponse = {
        "msr": args["msr"],
        "class_name": args["class_name"],
        "images": names,
        "total": len(names),
    }
    return jsonify(body)


@bp.get("/msr-image")
def serve_image_route():
    args = _require("eqp_ip", "class_name", "msr", "name")
    if args is None:
        return jsonify({"error": "eqp_ip, class_name, msr, name are required"}), 400
    if len(args["name"]) > 256:
        return jsonify({"error": "name too long"}), 400
    cfg = load_config()
    locator = ImageLocator(args["eqp_ip"], args["class_name"], args["msr"], args["name"])
    try:
        validate_tool_ip(args["eqp_ip"], cfg.allowed_subnets)
        validate_locator(args["class_name"], args["msr"], args["name"])
        cache = _get_cache(cfg)  # may raise ConfigError (office misconfig)
        fetched = cache.get(locator)
        if fetched is None:
            fetched = data.fetch_image(locator)
            cache.put(locator, fetched)
    except MsrImageError as exc:
        return _error(exc)

    headers = {"Cache-Control": "public, max-age=3600"}
    if fetched.cond is not None:
        headers["X-Msr-Cond"] = quote(fetched.cond)
    return Response(fetched.data, mimetype=fetched.content_type, headers=headers)


def _run_download(eqp_ip, class_name, msr, job_id, cache, concurrency, registry, names=None):
    """Own the whole tool round-trip: list (when unscoped), then fetch.

    The listing lives here rather than in the request handler because office-side
    it is an FTP call to the tool — the slowest step — and the client should not
    hold a connection open waiting for it. The job exists before this runs, so
    both the size and any failure are reported through polling. A caller that
    already knows which files it wants (the parameter-scoped cache warmer)
    passes ``names`` and skips the listing entirely.

    ``registry`` is handed in rather than resolved here: this thread has no app
    context, and the poll must read back the very store the POST wrote to."""

    def on_file(name, fetched, error):
        if fetched is not None:
            cache.put(ImageLocator(eqp_ip, class_name, msr, name), fetched)
            registry.record_ok(job_id)
        else:
            registry.record_failure(job_id, name, error or "unknown error")

    try:
        if names is None:
            names = data.list_images(eqp_ip, class_name, msr)
        registry.set_total(job_id, len(names))
        data.download_all(eqp_ip, class_name, msr, names, on_file, concurrency)
    except Exception:
        # A whole-job failure (the listing, or the download as a whole — not a
        # per-file one, which on_file records) ends the job in "error", not
        # "done": the poll must never report a failed job as a success.
        registry.mark_error(job_id)
    else:
        registry.finish(job_id)


# A scoped warm names at most one parameter's points; anything past this is a
# malformed caller, not a big parameter.
_MAX_JOB_NAMES = 500


@bp.post("/msr-images")
def download_all_route():
    payload = request.get_json(silent=True) or {}
    eqp_ip = str(payload.get("eqp_ip") or "").strip()
    class_name = str(payload.get("class_name") or "").strip()
    msr = str(payload.get("msr") or "").strip()
    if not (eqp_ip and class_name and msr):
        return jsonify({"error": "eqp_ip, class_name, msr are required"}), 400

    # Optional scope: fetch exactly these files instead of listing the whole
    # tool directory. [] and absent both mean "everything" — the caller sending
    # an empty scope wants the old behavior, not a no-op job.
    raw_names = payload.get("names")
    names = None
    if raw_names is not None:
        if not isinstance(raw_names, list) or not all(isinstance(n, str) for n in raw_names):
            return jsonify({"error": "names must be a list of strings"}), 400
        if len(raw_names) > _MAX_JOB_NAMES:
            return jsonify({"error": f"names capped at {_MAX_JOB_NAMES}"}), 400
        stripped = [n.strip() for n in raw_names if n.strip()]
        names = stripped or None

    cfg = load_config()
    registry = make_registry(cfg, data.provider_name())
    # Cheap fast-path: refuse before the (slow) FTP listing when already at cap.
    # The authoritative gate is the atomic create_bounded below (spec §9).
    if registry.running_count() >= cfg.max_jobs:
        return jsonify({"error": "too many active downloads", "code": "too_many_jobs"}), 429
    # Only the cheap, local checks run here — a malformed request still earns a
    # synchronous 4xx/5xx. Anything that touches the tool is the worker's job.
    try:
        validate_tool_ip(eqp_ip, cfg.allowed_subnets)
        validate_segment(class_name, "class_name")
        validate_segment(msr, "msr")
        for n in names or []:
            if len(n) > 256:
                return jsonify({"error": "name too long"}), 400
            validate_locator(class_name, msr, n)
        cache = _get_cache(cfg)  # may raise ConfigError (office misconfig)
    except MsrImageError as exc:
        return _error(exc)

    # total starts unknown (0): the listing that determines it has not run yet.
    # The worker calls set_total once it lands, so a poll before then reports a
    # running job of unknown size rather than a wrong one.
    job_id = registry.create_bounded(total=0, max_running=cfg.max_jobs)
    if job_id is None:
        return jsonify({"error": "too many active downloads", "code": "too_many_jobs"}), 429
    thread = threading.Thread(
        target=_run_download,
        args=(eqp_ip, class_name, msr, job_id, cache, cfg.ftp_concurrency, registry, names),
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id}), 202


@bp.get("/msr-images/<job_id>")
def poll_job_route(job_id: str):
    st = make_registry(load_config(), data.provider_name()).get(job_id)
    if st is None:
        return jsonify({"error": "unknown job", "code": "unknown_job"}), 404
    return jsonify(st)
