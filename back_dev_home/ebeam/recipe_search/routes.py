from flask import Blueprint, Response, current_app, jsonify, request

from back_dev_home._core.request_args import (
    resolve_fab_name,
    resolve_fab_names,
)
from back_dev_home._logging.activity import promote_request_fab_names
from back_dev_home.ebeam._slug_routes import (
    bad_tool_slug_response,
    resolve_sem_tool_type,
)
from back_dev_home.ebeam.recipe_search import param_info
from back_dev_home.ebeam.recipe_search.contracts import (
    CompareRequestItem,
    IdpLocator,
    ParamDetailRequestItem,
)
from back_dev_home.ebeam.recipe_search.data import (
    ToolType,
    check_recipe_registry,
    fetch_recipe_image,
    get_align_detail,
    get_align_images,
    get_param_detail,
    get_recipe_catalog,
    get_recipe_compare_data,
    get_recipe_open_data,
)
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.recipe_search import rawfiles
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import FetchedImage
from back_dev_home.msr_image.errors import InvalidLocator, MsrImageError
from back_dev_home.msr_image.paths import validate_segment, validate_tool_ip
from back_dev_home.msr_image.preview import preview_bytes, wants_preview
from back_dev_home.msr_image.single_flight import single_flight


bp = Blueprint("recipe_search", __name__)


def _get_cache(cfg):
    """One cache per (app, provider), as msr_image does.

    Rebuilding it per request would, office-side, build a fresh MinIO SDK
    client and connection pool for every thumbnail in a recipe.
    """
    provider = get_data_provider("recipe_search")
    key = f"recipe_image_cache::{provider}"
    ext = current_app.extensions
    cache = ext.get(key)
    if cache is None:
        cache = make_cache(cfg, provider, key_fn=rawfiles.recipe_image_cache_key)
        ext[key] = cache
    return cache

# Compare fans one parameter out across every selected recipe, so the
# param-detail body is a LIST. As N separate GETs a large comparison could
# exhaust the shared 50 requests / 5 s per-user budget on /api/*; as one POST
# it is one request. Same cap the compare endpoint already applies.
#
# One name, one value: param-info builds items against the same ceiling, and a
# second literal here would let the two drift.
_MAX_PARAM_ITEMS = param_info.MAX_OCCURRENCES

# The locator's path segments. eqp_ip is validated separately — it is an IP, and
# the guard it needs is the SSRF one, not the traversal one.
_LOCATOR_SEGMENTS = ("class_name", "idw", "idp")

# Each align point costs two FTP paths. A recipe has roughly ten; the cap is a
# ceiling on what a client can make the backend ask a tool for, not a limit any
# real recipe approaches.
_MAX_ALIGN_POINTS = 200

# Both POST bodies that carry a recipe LIST share this ceiling. Compare fans
# FTP work out per recipe and registry-check does two Redis reads per recipe,
# so the two are nowhere near equally expensive — they share a cap because it
# is a ceiling on request SIZE, and one number is one thing to reason about.
_MAX_RECIPE_ITEMS = 200


def _resolve_tool_type(tool_slug: str) -> ToolType | None:
    return resolve_sem_tool_type(tool_slug)


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


def _resolve_recipe_request(tool_slug: str, *, needs_parameter: bool):
    """The preamble the three tiered read routes share.

    Returns ``(context, None)`` or ``(None, coded_response)``, where context is
    ``(tool_type, recipe_name, parameter, fab_name)``. Written once because the
    404 semantics below are argued for at length and were being copied verbatim
    into each new route — the kind of duplication that drifts silently, since
    nothing fails when one copy's message or status stops matching the others.
    """
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return None, bad_tool_slug_response()

    recipe_name = (request.args.get("recipe_name") or "").strip()
    parameter = (request.args.get("parameter") or "").strip()
    if not recipe_name:
        return None, (jsonify({"error": "recipe_name is required"}), 400)
    if needs_parameter and not parameter:
        return None, (jsonify({"error": "parameter is required"}), 400)

    return (tool_type, recipe_name, parameter, resolve_fab_name()), None


def _recipe_items():
    """The `{"recipes": [{recipe_name, fab_name}, ...]}` body, validated.

    Returns ``(items, None)`` or ``(None, coded_response)``. Shared by compare
    and registry-check rather than copied into the second: the two bodies are
    the same body, and a validation rule that lives in two places is a rule
    that ends up applying in one.
    """
    payload = request.get_json(silent=True) or {}
    raw_recipes = payload.get("recipes")
    if not isinstance(raw_recipes, list) or not raw_recipes:
        return None, (jsonify({"error": "recipes must be a non-empty list"}), 400)
    if len(raw_recipes) > _MAX_RECIPE_ITEMS:
        return None, (jsonify({
            "error": f"recipes exceeds the {_MAX_RECIPE_ITEMS}-recipe limit"
        }), 400)

    recipes: list[CompareRequestItem] = []
    for item in raw_recipes:
        if not isinstance(item, dict):
            return None, (jsonify({"error": "recipes items must be objects"}), 400)
        name = str(item.get("recipe_name") or "").strip()
        if not name:
            return None, (jsonify({"error": "recipes items need a recipe_name"}), 400)
        fab = str(item.get("fab_name") or "").strip().upper()
        recipes.append({"recipe_name": name, "fab_name": fab})
    return recipes, None


def _parameter_missing(parameter: str):
    """404 on the PARAMETER, not on an empty result.

    A parameter can legitimately have no measurement point, so collapsing the
    two would report a typo'd name as "no points" — an answer that looks like
    data rather than a mistake.
    """
    return jsonify({"error": f"parameter not in recipe: {parameter}"}), 404


@bp.errorhandler(MsrImageError)
def _handle_msr_image_error(exc: MsrImageError):
    """Every route in this blueprint answers an unreachable tool the same way.

    Registered rather than repeated because ``get_recipe_open_data`` is I/O at
    the office too — locating the .idp can touch the tool — so ``recipes`` and
    ``recipe-detail`` could raise it just as the raw-folder routes can, and
    those two had no guard: an unreachable tool escaped as a 500 traceback on
    the feature's most-used endpoint.

    Uses ``_error`` rather than ``_auth.errors.error_json`` deliberately: this
    surface's body is flat (``{"error", "code"}``) and the app-wide helper nests
    under ``error``. Handing this to the shared helper would have quietly
    changed the response shape for every existing tool-FTP caller.
    """
    return _error(exc)


@bp.get("/<tool_slug>/recipe-search/recipes")
def recipe_search_recipes(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return bad_tool_slug_response()

    fab_names = resolve_fab_names()
    promote_request_fab_names(*fab_names)
    return jsonify(get_recipe_catalog(tool_type, fab_names or None))


@bp.get("/<tool_slug>/recipe-search/recipe-detail")
def recipe_search_recipe_detail(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return bad_tool_slug_response()

    recipe_name = (request.args.get("recipe_name") or "").strip()
    if not recipe_name:
        return jsonify({"error": "recipe_name is required"}), 400

    return jsonify(get_recipe_open_data(
        recipe_id=recipe_name,
        fab_name=resolve_fab_name(),
        tool_category=tool_type
    ))


@bp.get("/<tool_slug>/recipe-search/parameters")
def recipe_search_parameters(tool_slug: str):
    """Tier 0 — every idp_image_info row of one recipe. No tool I/O.

    A strict, cheaper subset of recipe-detail, for callers that want the
    parameter listing without the measurement and align tables. The locator is
    returned so a caller can drop straight into POST param-detail for bulk work
    without a second recipe-detail call.
    """
    context, failed = _resolve_recipe_request(tool_slug, needs_parameter=False)
    if failed:
        return failed
    tool_type, recipe_name, _, fab_name = context

    detail = get_recipe_open_data(
        recipe_id=recipe_name, fab_name=fab_name, tool_category=tool_type
    )
    return jsonify(param_info.build_parameter_list(detail, tool_type, fab_name))


@bp.get("/<tool_slug>/recipe-search/measurement-points")
def recipe_search_measurement_points(tool_slug: str):
    """Tier 1 — wafer_mp_info for one parameter. No tool I/O.

    ``parameter`` is required: the unfiltered table is what recipe-detail
    already returns.
    """
    context, failed = _resolve_recipe_request(tool_slug, needs_parameter=True)
    if failed:
        return failed
    tool_type, recipe_name, parameter, fab_name = context

    detail = get_recipe_open_data(
        recipe_id=recipe_name, fab_name=fab_name, tool_category=tool_type
    )
    if not param_info.rows_for_parameter(detail, parameter):
        return _parameter_missing(parameter)

    return jsonify(param_info.build_measurement_points(detail, parameter))


@bp.get("/<tool_slug>/recipe-search/param-info")
def recipe_search_param_info(tool_slug: str):
    """Tier 2 — raw-recipe-folder settings for one parameter.

    ``occurrences`` is a list because a parameter can occupy several
    idp_image_info rows naming different files. ``include`` narrows what is
    READ, not merely what is returned — see ``param_info._PART_SLOTS``.
    """
    context, failed = _resolve_recipe_request(tool_slug, needs_parameter=True)
    if failed:
        return failed
    tool_type, recipe_name, parameter, fab_name = context

    try:
        include = param_info.parse_include(request.args.get("include"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    detail = get_recipe_open_data(
        recipe_id=recipe_name, fab_name=fab_name, tool_category=tool_type
    )
    rows = param_info.rows_for_parameter(detail, parameter)
    if not rows:
        return _parameter_missing(parameter)

    # An unreachable tool raises SourceUnavailable from deep in the FTP layer
    # and is answered by the blueprint's MsrImageError handler.
    return jsonify(param_info.build_param_info(
        detail, parameter, tool_type, fab_name, include, get_param_detail, rows
    ))


@bp.post("/<tool_slug>/recipe-search/compare")
def recipe_search_compare(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return bad_tool_slug_response()

    recipes, failed = _recipe_items()
    if failed:
        return failed

    promote_request_fab_names(*(item["fab_name"] for item in recipes))
    return jsonify(get_recipe_compare_data(tool_type, recipes))


@bp.post("/<tool_slug>/recipe-search/registry-check")
def recipe_search_registry_check(tool_slug: str):
    """Is each of these recipes backed by the Redis recipe registry?

    The frontend used catalog-list membership as a proxy for this, because the
    search table is built from that list and nothing else could be asked. The
    proxy is wrong in both directions — the catalog hash and the location
    registry are written by different upstream jobs — so the recipes it refused
    to open included ones the office could have opened.

    POST rather than GET for the reason compare is: the caller asks about a
    page of results at once, and 50 GETs would spend the whole 50 req / 5 s
    budget on a question worth one request.
    """
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return bad_tool_slug_response()

    recipes, failed = _recipe_items()
    if failed:
        return failed

    promote_request_fab_names(*(item["fab_name"] for item in recipes))
    return jsonify(check_recipe_registry(tool_type, recipes))


@bp.post("/<tool_slug>/recipe-search/param-detail")
def recipe_search_param_detail(tool_slug: str):
    """AMP, AF/PR and per-image beam conditions for one or more parameters.

    POST rather than GET because compare sends one item per recipe; see
    ``_MAX_PARAM_ITEMS``.
    """
    if not _resolve_tool_type(tool_slug):
        return bad_tool_slug_response()

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

    # The provider call is inside the guard too: a tool that refuses the
    # connection raises SourceUnavailable from deep in the FTP layer, and
    # without this it would surface as a 500 traceback instead of the coded
    # 503 the rest of the tool-FTP surface returns.
    try:
        return jsonify(get_param_detail(clean))
    except MsrImageError as exc:
        return _error(exc)


@bp.get("/<tool_slug>/recipe-search/align-detail")
def recipe_search_align_detail(tool_slug: str):
    """Every wafer-align point's image, beam condition and AF/PR setting.

    All points at once rather than one per request: a recipe has roughly ten,
    the popup shows them together, and ten GETs would trip the rate limit.
    """
    if not _resolve_tool_type(tool_slug):
        return bad_tool_slug_response()
    try:
        locator = _validated_locator(request.args.to_dict())
    except MsrImageError as exc:
        return _error(exc)

    raw = (request.args.get("p_numbers") or "").strip()
    try:
        p_numbers = [int(part) for part in raw.split(",") if part.strip()]
    except ValueError:
        return jsonify({"error": "p_numbers must be comma-separated integers"}), 400
    if len(set(p_numbers)) > _MAX_ALIGN_POINTS:
        return jsonify({
            "error": f"p_numbers exceeds the {_MAX_ALIGN_POINTS}-point limit"
        }), 400

    try:
        return jsonify(get_align_detail(locator, p_numbers))
    except MsrImageError as exc:
        return _error(exc)


@bp.get("/<tool_slug>/recipe-search/align-images")
def recipe_search_align_images(tool_slug: str):
    """A recipe's align reference images (OM and SEM) as one tool holds them.

    Built for the live-alarm board: an ALIGNMENT FAIL names a tool and a
    recipe, and the engineer wants to see what that tool was trying to align
    to. ``eqp_id`` is therefore part of the question, not a filter — the
    answer says which tool it actually came from so a substitution is never
    silent.

    Resolution only; the tool is dialed by ``recipe-image`` when the bytes are
    asked for. Keeping the two apart matters here because the tool this runs
    against is, by definition, the one having trouble.
    """
    context, failed = _resolve_recipe_request(tool_slug, needs_parameter=False)
    if failed:
        return failed
    tool_type, recipe_name, _, fab_name = context

    eqp_id = (request.args.get("eqp_id") or "").strip()
    promote_request_fab_names(fab_name)
    try:
        return jsonify(get_align_images(tool_type, recipe_name, fab_name, eqp_id))
    except MsrImageError as exc:
        return _error(exc)


@bp.get("/<tool_slug>/recipe-search/recipe-image")
def recipe_search_recipe_image(tool_slug: str):
    """One raw-recipe image, streamed from memory.

    Bytes rather than base64-in-JSON: base64 inflates the payload by a third,
    blocks the JSON parse, and is invisible to the browser cache. Nothing is
    stored on this host — FTP to memory to response.
    """
    if not _resolve_tool_type(tool_slug):
        return bad_tool_slug_response()
    name = (request.args.get("name") or "").strip()
    # Same cap msr_image applies — an unbounded name is an unbounded FTP path.
    if len(name) > 256:
        return jsonify({"error": "name too long"}), 400
    try:
        locator = _validated_locator(request.args.to_dict())
        validate_segment(name, "name")
    except MsrImageError as exc:
        return _error(exc)

    cache = _get_cache(load_config())
    cached_locator = {**locator, "name": name}

    def _visit_tool() -> FetchedImage:
        # The leader re-reads first: an attempt that finished a moment ago has
        # already filled the cache, and this body runs after the wait.
        hit = cache.get(cached_locator)
        if hit is not None:
            return hit
        payload, content_type = fetch_recipe_image(locator, name)
        got = FetchedImage(payload, content_type, None)
        cache.put(cached_locator, got)
        return got

    try:
        fetched = cache.get(cached_locator)
        if fetched is None:
            # Two different herds, two different guards. The CACHE is what
            # makes the second viewer free — engineers open the same hot
            # ALIGNMENT FAIL one after another, and before this the route was
            # "FTP to memory to response" for every one of them. SINGLE_FLIGHT
            # is what collapses the simultaneous ones: the browser retries a
            # slow image at 2.5s and 5s, and a stalled FTP login holds a uWSGI
            # worker for as long as ftp_host_timeout under a harakiri only
            # twice that. The tool this runs against is, on the live-alarm
            # path, the one currently failing to align.
            fetched = single_flight(
                rawfiles.recipe_image_cache_key(cached_locator), _visit_tool
            )
        payload, content_type = fetched.data, fetched.content_type
    except MsrImageError as exc:
        # An unreachable TOOL is not a missing image. Collapsing both into 404
        # would tell the user the file does not exist when the tool is simply
        # down — caught before LookupError because it is the narrower case.
        return _error(exc)
    except LookupError:
        # A real 404, so <img> falls back to its own broken state instead of
        # trying to decode a JSON error body as a picture.
        return jsonify({"error": f"image not found: {name}"}), 404

    # ?preview=1 — same TIFF→WebP rendition msr_image serves; a no-op on the
    # JPEG files recipe folders have been observed to hold, but HV-SEM has
    # already broken one single-image assumption here (2026-08-08), so the
    # tif-only case is handled before it is observed rather than after.
    if wants_preview(request.args.get("preview")):
        payload, content_type = preview_bytes(payload, content_type)

    return Response(
        payload,
        mimetype=content_type,
        # A raw-recipe file never changes for a given recipe, so this is
        # genuinely immutable rather than merely cacheable — without it every
        # thumbnail costs a fresh FTP session to a production tool once an hour.
        headers={"Cache-Control": "public, max-age=31536000, immutable"}
    )
