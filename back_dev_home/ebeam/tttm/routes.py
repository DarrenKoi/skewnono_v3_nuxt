from flask import Blueprint, jsonify, request

from back_dev_home.ebeam._analysis_window import (
    bad_window_weeks_response,
    resolve_window_weeks,
)
from back_dev_home.ebeam._slug_routes import (
    bad_tool_slug_response,
    is_sem_tool_slug,
)
from back_dev_home.ebeam.tttm.data import get_tttm_check, get_tttm_recipes

bp = Blueprint("tttm", __name__)


def _arg(name: str) -> str | None:
    raw = (request.args.get(name) or "").strip()
    return raw or None


def _args(name: str) -> tuple[str, ...]:
    """Every non-blank value of a repeated query key, de-duplicated in order.

    `?parameter=a&parameter=b` is how the client sends a multi-select (ofetch
    serialises an array as a repeated key). Blanks are dropped the way `_arg`
    folds them to None — `?parameter=` is a cleared picker, not a parameter
    named empty.
    """
    seen: dict[str, None] = {}
    for raw in request.args.getlist(name):
        value = raw.strip()
        if value:
            seen.setdefault(value, None)
    return tuple(seen)


@bp.get("/<tool_slug>/tttm/check")
def tttm_check(tool_slug: str):
    if not is_sem_tool_slug(tool_slug):
        return bad_tool_slug_response()
    fab_name = _arg("fab_name")
    if fab_name is None:
        return jsonify({"error": "fab_name is required"}), 400
    recipe_id = _arg("recipe_id")
    parameters = _args("parameter")
    # A parameter name is a row of ONE recipe's idp_image_info, and the same
    # name in another recipe measures a different feature — so "this parameter,
    # across every recipe" is not a question with an answer. Refused rather than
    # ignored: a silently dropped filter returns a group verdict under a
    # parameter heading the server never applied, and nothing about that
    # response looks wrong to the client.
    if parameters and recipe_id is None:
        return jsonify({"error": "parameter requires recipe_id"}), 400
    # How far back to gather runs. Refused rather than clamped when it is not
    # one of the offered choices — see _analysis_window.resolve_window_weeks.
    window_weeks = resolve_window_weeks()
    if window_weeks is None:
        return bad_window_weeks_response()
    # The tools the user picked for the comparison — a repeated key the same
    # way `parameter` is, folded to a tuple by the same helper. `()` means the
    # whole fleet, the pre-existing behaviour; a non-empty tuple narrows the
    # fleet the skew is computed over (see contracts.narrow_fleet).
    eqp_ids = _args("eqp_id")
    payload = get_tttm_check(tool_slug, fab_name, recipe_id, parameters, window_weeks, eqp_ids)
    return jsonify(payload)


@bp.get("/<tool_slug>/tttm/recipes")
def tttm_recipes(tool_slug: str):
    """Recipes this fab has measured, for the shared pm-planning / TTTM picker.

    Same slug, fab_name and window_weeks rules as `/tttm/check`, so a fab that
    answers one answers the other — a picker scoped differently from the
    payload it drives would offer recipes the check then finds nothing for.
    """
    if not is_sem_tool_slug(tool_slug):
        return bad_tool_slug_response()
    fab_name = _arg("fab_name")
    if fab_name is None:
        return jsonify({"error": "fab_name is required"}), 400
    window_weeks = resolve_window_weeks()
    if window_weeks is None:
        return bad_window_weeks_response()
    return jsonify(get_tttm_recipes(tool_slug, fab_name, window_weeks))
