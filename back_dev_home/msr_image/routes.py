"""msr_image blueprint. Phase-agnostic: assembles locators, delegates bytes to
the data seam, caches, and relays. Office knowledge is only in providers/office."""

import threading
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import ImageListResponse, ImageLocator
from back_dev_home.msr_image.errors import MsrImageError
from back_dev_home.msr_image.jobs import default_registry
from back_dev_home.msr_image.paths import validate_tool_ip

bp = Blueprint("msr_image", __name__)


def _error(exc: MsrImageError):
    return jsonify({"error": str(exc) or exc.code, "code": exc.code}), exc.status


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
    try:
        validate_tool_ip(args["eqp_ip"], cfg.allowed_subnets)
    except MsrImageError as exc:
        return _error(exc)

    locator = ImageLocator(args["eqp_ip"], args["class_name"], args["msr"], args["name"])
    cache = make_cache(cfg, data.provider_name())
    fetched = cache.get(locator)
    if fetched is None:
        try:
            fetched = data.fetch_image(locator)
        except MsrImageError as exc:
            return _error(exc)
        cache.put(locator, fetched)

    headers = {"Cache-Control": "public, max-age=3600"}
    if fetched.cond is not None:
        headers["X-Msr-Cond"] = quote(fetched.cond)
    return Response(fetched.data, mimetype=fetched.content_type, headers=headers)


def _run_download(app, eqp_ip, class_name, msr, names, job_id):
    cfg = load_config()
    cache = make_cache(cfg, data.provider_name())
    registry = default_registry()

    def on_file(name, fetched, error):
        if fetched is not None:
            cache.put(ImageLocator(eqp_ip, class_name, msr, name), fetched)
            registry.record_ok(job_id)
        else:
            registry.record_failure(job_id, name, error or "unknown error")

    try:
        data.download_all(eqp_ip, class_name, msr, names, on_file, cfg.ftp_concurrency)
    finally:
        registry.finish(job_id)


@bp.post("/msr-images")
def download_all_route():
    payload = request.get_json(silent=True) or {}
    eqp_ip = str(payload.get("eqp_ip") or "").strip()
    class_name = str(payload.get("class_name") or "").strip()
    msr = str(payload.get("msr") or "").strip()
    if not (eqp_ip and class_name and msr):
        return jsonify({"error": "eqp_ip, class_name, msr are required"}), 400

    cfg = load_config()
    try:
        validate_tool_ip(eqp_ip, cfg.allowed_subnets)
        names = data.list_images(eqp_ip, class_name, msr)
    except MsrImageError as exc:
        return _error(exc)

    registry = default_registry()
    job_id = registry.create(total=len(names))
    thread = threading.Thread(
        target=_run_download,
        args=(None, eqp_ip, class_name, msr, names, job_id),
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id}), 202


@bp.get("/msr-images/<job_id>")
def poll_job_route(job_id: str):
    st = default_registry().get(job_id)
    if st is None:
        return jsonify({"error": "unknown job", "code": "unknown_job"}), 404
    return jsonify(st)
