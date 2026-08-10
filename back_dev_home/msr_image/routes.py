"""msr_image blueprint. Phase-agnostic: assembles locators, delegates bytes to
the data seam, caches, and relays. Office knowledge is only in providers/office."""

import threading
from urllib.parse import quote

from flask import Blueprint, Response, current_app, jsonify, request

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import cache_key, make_cache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import FetchedImage, ImageListResponse, ImageLocator
from back_dev_home.msr_image.errors import MsrImageError
from back_dev_home.msr_image.jobs import make_registry
from back_dev_home.msr_image.paths import validate_locator, validate_segment, validate_tool_ip
from back_dev_home.msr_image.preview import to_preview, wants_preview
from back_dev_home.msr_image.single_flight import single_flight

bp = Blueprint("msr_image", __name__)


def _wants_preview() -> bool:
    return wants_preview(request.args.get("preview"))

# Tools are not consistent about which spelling they write -- office serves
# .jpeg/.jpg/.tif/.tiff (MIGRATION.md, office 확인 2026-07-24) while the mock
# emits only .jpeg/.tif. Grouping means a caller never has to know which
# spelling a given tool happened to use.
_EXT_GROUPS: dict[str, tuple[str, ...]] = {
    "jpg": (".jpg", ".jpeg"),
    "tif": (".tif", ".tiff"),
}


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


# Extensions for the types the preview transform can PRODUCE.
_RENDITION_EXTS = {"image/webp": ".webp", "image/svg+xml": ".svg"}


def _served_name(name: str, converted_to: str | None) -> str:
    """The filename that matches the bytes actually being served.

    ``?preview=1`` on a TIFF sends WebP, and naming those bytes ``.tif`` in
    Content-Disposition misleads anyone who saves the response directly — the
    file will not open as the extension claims. The disposition stays
    ``inline``; only the name is corrected.

    ``converted_to`` is the new content type when the preview transform
    actually changed it, else None. Gating on the CONVERSION rather than on the
    outgoing type matters: the download path must keep the tool's own filename
    verbatim, and at home the mock serves SVG bytes under a ``.jpeg`` name, so
    a type-only check would rename a file nobody converted.
    """
    ext = _RENDITION_EXTS.get(converted_to or "")
    if ext is None or name.lower().endswith(ext):
        return name
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return f"{stem}{ext}"


def _content_disposition(name: str) -> str:
    """RFC 6266 disposition for a caller-supplied image filename.

    ``inline``, not ``attachment``: the gallery reads these bytes through
    ``<img :src>`` and ``fetch()`` + blob, and inline is neutral for both
    while ``curl -OJ`` still picks the filename up either way. The target
    audience is Python and curl, so attachment would add browser-behavior
    risk for no gain.

    Both parameter forms are emitted. ``validate_locator`` rejects ``/``,
    ``\\`` and control chars but NOT a double quote, so the quoted-string
    form is escaped rather than trusted; and a non-ASCII name cannot ride
    in it at all, because Werkzeug encodes header values as latin-1 and
    raises on anything else.
    """
    ascii_name = name.encode("ascii", "replace").decode("ascii")
    escaped = ascii_name.replace("\\", "\\\\").replace('"', '\\"')
    return f"inline; filename=\"{escaped}\"; filename*=UTF-8''{quote(name, safe='')}"


@bp.get("/msr-images")
def list_images_route():
    args = _require("eqp_ip", "class_name", "msr")
    if args is None:
        return jsonify({"error": "eqp_ip, class_name, msr are required"}), 400
    cfg = load_config()
    ext = (request.args.get("ext") or "").strip().lower()
    if ext and ext not in _EXT_GROUPS:
        allowed = ", ".join(sorted(_EXT_GROUPS))
        return jsonify({"error": f"unknown ext {ext!r}; allowed: {allowed}"}), 400
    try:
        validate_tool_ip(args["eqp_ip"], cfg.allowed_subnets)
        validate_segment(args["class_name"], "class_name")
        validate_segment(args["msr"], "msr")
        names = data.list_images(args["eqp_ip"], args["class_name"], args["msr"])
    except MsrImageError as exc:
        return _error(exc)
    if ext:
        suffixes = _EXT_GROUPS[ext]
        names = [n for n in names if n.lower().endswith(suffixes)]
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
    preview = _wants_preview()
    # The content type the preview transform PRODUCED, when it changed one; None
    # on the plain path. Drives the served filename — see _served_name.
    converted_to = None
    try:
        validate_tool_ip(args["eqp_ip"], cfg.allowed_subnets)
        validate_locator(args["class_name"], args["msr"], args["name"])
        cache = _get_cache(cfg)  # may raise ConfigError (office misconfig)

        # ?preview=1 — a browser-renderable rendition (TIFF → WebP, by content
        # sniff; everything else untouched). The 원본 다운로드 link omits the
        # flag and reads the same locator. See msr_image/preview.py.
        #
        # The rendition has its own cache entry, so ask for it FIRST: conversion
        # is the expensive half of a preview request (TIFF decode, float64
        # percentile stretch, WebP encode — all GIL-bound on a worker thread),
        # and before renditions were cached it ran on every single GET. The
        # originals entry is untouched by this, so a preview still never costs
        # a second tool fetch and the download path still finds its TIFF.
        fetched = cache.get(locator, preview=True) if preview else None
        if fetched is not None:
            # A rendition is only ever in the cache because a conversion made
            # it — which is exactly what _served_name needs to know.
            converted_to = fetched.content_type
        else:
            fetched = cache.get(locator)
            if fetched is None:
                # One visit to the tool per image, however many requests want
                # it: the browser's own 2.5s/5s retries and a second viewer all
                # land here while the first fetch is still running, and they
                # consume its result instead of opening their own session.
                # Keyed on the ORIGINAL (preview=False) because a preview and a
                # download of the same image are one tool visit; the TIFF->WebP
                # conversion below is our CPU, not the tool's, and stays
                # outside.
                #
                # The re-read below is the leader's, not a waiter's: an attempt
                # that finished a moment ago has already filled the cache. And
                # when the fetch RAISES, single_flight re-raises that same
                # error in the waiters — the cache stays empty on failure, so
                # they would otherwise queue up for their own turn at a sick
                # tool. It is the real exception, so the except below maps it
                # as usual.
                def visit_tool() -> FetchedImage:
                    hit = cache.get(locator)
                    if hit is not None:
                        return hit
                    got = data.fetch_image(locator)
                    cache.put(locator, got)
                    return got

                fetched = single_flight(cache_key(locator), visit_tool)
            if preview:
                rendition = to_preview(fetched)
                if rendition.content_type != fetched.content_type:
                    converted_to = rendition.content_type
                    # Cache only a real TIFF → WebP conversion. to_preview's
                    # other branches (the mock's SVG-labeled-as-TIFF relabel,
                    # and the untouched passthrough) hand back the SAME bytes,
                    # so storing them would buy nothing and would park non-WebP
                    # bytes under a key named ``.preview.webp``.
                    if rendition.content_type == "image/webp":
                        cache.put(locator, rendition, preview=True)
                fetched = rendition
    except MsrImageError as exc:
        return _error(exc)

    headers = {
        "Cache-Control": "public, max-age=3600",
        "Content-Disposition": _content_disposition(
            _served_name(args["name"], converted_to)
        ),
    }
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
        else:
            # A scoped warm re-fires per parameter switch and after refusals;
            # don't pull files the cache already holds from the tool again.
            names = [
                n for n in names
                if not cache.has(ImageLocator(eqp_ip, class_name, msr, n))
            ]
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
    if raw_names is not None:
        if not isinstance(raw_names, list) or not all(isinstance(n, str) for n in raw_names):
            return jsonify({"error": "names must be a list of strings"}), 400
        if len(raw_names) > _MAX_JOB_NAMES:
            return jsonify({"error": f"names capped at {_MAX_JOB_NAMES}"}), 400
    names = raw_names or None

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
            validate_segment(n, "name")  # class_name/msr are validated once above
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
