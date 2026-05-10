from flask import Blueprint, g, jsonify, request

from .data import get_leaderboard, get_me

bp = Blueprint("activity", __name__)


def _viewer() -> str:
    return getattr(g, "user_id", None) or request.cookies.get("LASTUSER") or "local-dev"


@bp.get("/activity/me")
def activity_me():
    return jsonify(get_me(_viewer()))


@bp.get("/activity/leaderboard")
def activity_leaderboard():
    try:
        top_n = max(1, min(50, int(request.args.get("top", 10))))
    except (TypeError, ValueError):
        top_n = 10
    return jsonify(get_leaderboard(_viewer(), top_n=top_n))
