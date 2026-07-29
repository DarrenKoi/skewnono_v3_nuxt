from flask import Blueprint, Response, jsonify, request

from back_dev_home._logging.activity import promote_request_fab_names
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    IdpLocator,
    ParamDetailRequestItem,
)
from back_dev_home.ebeam.hitachi.recipe_search.data import (
    ToolType,
    fetch_recipe_image,
    get_align_detail,
    get_param_detail,
    get_recipe_catalog,
    get_recipe_compare_data,
    get_recipe_open_data,
)
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.errors import InvalidLocator, MsrImageError
from back_dev_home.msr_image.paths import validate_segment, validate_tool_ip


bp = Blueprint("ebeam_recipe_search", __name__)

TOOL_BY_SLUG: dict[str, ToolType] = {
    "cdsem": "cd-sem",
    "hvsem": "hv-sem"
}

# Compare fans one parameter out across every selected recipe, so the
# param-detail body is a LIST. As N separate GETs this would trip the
# 20 requests / 5 s per-user limit on /api/* the moment a user compared more
# than a handful of recipes; as one POST it is one request. Same cap the
# compare endpoint already applies.
_MAX_PARAM_ITEMS = 200

# The locator's path segments. eqp_ip is validated separately — it is an IP, and
# the guard it needs is the SSRF one, not the traversal one.
_LOCATOR_SEGMENTS = ("class_name", "idw", "idp")


def _resolve_tool_type(tool_slug: str) -> ToolType | None:
    return TOOL_BY_SLUG.get(tool_slug.strip().lower())


def _error(exc: MsrImageError):
    """msr_image's error shape, reused verbatim.

    Catching the base class rather than the two guard subclasses matters: a
    ``ConfigError`` from ``load_config()`` on a misconfigured office box would
    otherwise escape as a 500 traceback instead of the coded response the rest
    of the tool-FTP surface returns.
    """
    return jsonify({"error": str(exc) or exc.code, "code": exc.code}), exc.status


def _validated_locator(raw: object, allowed_subnets: list[str] | None = None) -> IdpLocator:
    """Guard the four client-supplied FTP path fields.

    The backend opens an FTP session to whatever this names, so both guards are
    load-bearing rather than defensive: ``validate_tool_ip`` is the SSRF gate
    and ``validate_segment`` stops a ``..`` escaping the raw-recipe folder.
    Both are reused from msr_image, which faces the identical exposure.

    ``allowed_subnets`` is passed in rather than read here because param-detail
    validates up to 200 items per request, and ``load_config()`` re-parses the
    environment on every call.

    Raises:
        InvalidLocator, InvalidToolIp: rejected by one of the two guards.
    """
    if not isinstance(raw, dict):
        raise InvalidLocator("locator must be an object")
    locator: IdpLocator = {
        key: str(raw.get(key) or "").strip()
        for key in ("eqp_ip", "class_name", "idw", "idp")
    }
    validate_tool_ip(
        locator["eqp_ip"],
        load_config().allowed_subnets if allowed_subnets is None else allowed_subnets,
    )
    for key in _LOCATOR_SEGMENTS:
        validate_segment(locator[key], key)
    return locator


def _resolve_fab_name() -> str | None:
    raw = (request.args.get("fab_name") or "").strip().upper()
    return raw or None


@bp.get("/<tool_slug>/recipe-search/recipes")
def recipe_search_recipes(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    return jsonify(get_recipe_catalog(tool_type, _resolve_fab_name()))


@bp.get("/<tool_slug>/recipe-search/recipe-detail")
def recipe_search_recipe_detail(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    recipe_name = (request.args.get("recipe_name") or "").strip()
    if not recipe_name:
        return jsonify({"error": "recipe_name is required"}), 400

    return jsonify(get_recipe_open_data(
        recipe_id=recipe_name,
        fac_id=_resolve_fab_name(),
        tool_category=tool_type
    ))


@bp.post("/<tool_slug>/recipe-search/compare")
def recipe_search_compare(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    payload = request.get_json(silent=True) or {}
    recipe_names = payload.get("recipe_names")
    if not isinstance(recipe_names, list) or not recipe_names:
        return jsonify({"error": "recipe_names must be a non-empty list"}), 400

    if len(recipe_names) > 200:
        return jsonify({"error": "recipe_names exceeds the 200-recipe limit"}), 400

    fab_name = (payload.get("fab_name") or "").strip().upper() or None
    promote_request_fab_names(fab_name)
    return jsonify(
        get_recipe_compare_data(tool_type, fab_name, [str(name) for name in recipe_names])
    )


@bp.post("/<tool_slug>/recipe-search/param-detail")
def recipe_search_param_detail(tool_slug: str):
    """AMP, AF/PR and per-image beam conditions for one or more parameters.

    POST rather than GET because compare sends one item per recipe; see
    ``_MAX_PARAM_ITEMS``.
    """
    if not _resolve_tool_type(tool_slug):
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "items must be a non-empty list"}), 400
    if len(items) > _MAX_PARAM_ITEMS:
        return jsonify({"error": f"items exceeds the {_MAX_PARAM_ITEMS}-item limit"}), 400

    clean: list[ParamDetailRequestItem] = []
    try:
        allowed_subnets = load_config().allowed_subnets
        for item in items:
            if not isinstance(item, dict):
                raise InvalidLocator("each item must be an object")
            raw_slots = item.get("slots") or {}
            if not isinstance(raw_slots, dict):
                raise InvalidLocator("slots must be an object")
            slots = {
                str(key): str(value or "").strip()
                for key, value in raw_slots.items()
            }
            for key, value in slots.items():
                # "non" is a legitimate value and passes validate_segment
                # unchanged; only separators and control characters are
                # rejected. An empty value is simply an absent slot.
                if value:
                    validate_segment(value, key)
            clean.append({
                "locator": _validated_locator(item.get("locator"), allowed_subnets),
                "parameter": str(item.get("parameter") or "").strip(),
                "slots": slots
            })
    except MsrImageError as exc:
        return _error(exc)

    return jsonify(get_param_detail(clean))


@bp.get("/<tool_slug>/recipe-search/align-detail")
def recipe_search_align_detail(tool_slug: str):
    """Every wafer-align point's image, beam condition and AF/PR setting.

    All points at once rather than one per request: a recipe has roughly ten,
    the popup shows them together, and ten GETs would trip the rate limit.
    """
    if not _resolve_tool_type(tool_slug):
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    try:
        locator = _validated_locator(request.args.to_dict())
    except MsrImageError as exc:
        return _error(exc)

    raw = (request.args.get("p_numbers") or "").strip()
    try:
        p_numbers = [int(part) for part in raw.split(",") if part.strip()]
    except ValueError:
        return jsonify({"error": "p_numbers must be comma-separated integers"}), 400

    return jsonify(get_align_detail(locator, p_numbers))


@bp.get("/<tool_slug>/recipe-search/recipe-image")
def recipe_search_recipe_image(tool_slug: str):
    """One raw-recipe image, streamed from memory.

    Bytes rather than base64-in-JSON: base64 inflates the payload by a third,
    blocks the JSON parse, and is invisible to the browser cache. Nothing is
    stored on this host — FTP to memory to response.
    """
    if not _resolve_tool_type(tool_slug):
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    name = (request.args.get("name") or "").strip()
    # Same cap msr_image applies — an unbounded name is an unbounded FTP path.
    if len(name) > 256:
        return jsonify({"error": "name too long"}), 400
    try:
        locator = _validated_locator(request.args.to_dict())
        validate_segment(name, "name")
    except MsrImageError as exc:
        return _error(exc)

    try:
        payload, content_type = fetch_recipe_image(locator, name)
    except LookupError:
        # A real 404, so <img> falls back to its own broken state instead of
        # trying to decode a JSON error body as a picture.
        return jsonify({"error": f"image not found: {name}"}), 404

    return Response(
        payload,
        mimetype=content_type,
        # A raw-recipe file never changes for a given recipe, so this is
        # genuinely immutable rather than merely cacheable — without it every
        # thumbnail costs a fresh FTP session to a production tool once an hour.
        headers={"Cache-Control": "public, max-age=31536000, immutable"}
    )
