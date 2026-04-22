from flask import Blueprint, jsonify

from .data import get_sem_list

bp = Blueprint("sem_list", __name__)


@bp.get("/sem-list")
def sem_list():
    rows = get_sem_list()
    return jsonify(rows)
