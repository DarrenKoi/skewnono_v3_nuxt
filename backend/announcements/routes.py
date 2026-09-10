from flask import Blueprint, jsonify

from backend.announcements.data import get_announcements

bp = Blueprint("announcements", __name__)


@bp.get("/announcements")
def announcements():
    return jsonify(get_announcements())
