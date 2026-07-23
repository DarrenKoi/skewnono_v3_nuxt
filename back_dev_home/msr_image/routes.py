"""msr_image blueprint. Phase-agnostic: assembles locators, delegates bytes to
the data seam, caches, and relays. Office knowledge is only in providers/office."""

from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import ImageListResponse, ImageLocator
from back_dev_home.msr_image.errors import MsrImageError
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
