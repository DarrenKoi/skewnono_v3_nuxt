from flask import Blueprint, jsonify

from back_dev_home.sem_list.data import get_sem_list

bp = Blueprint("sem_list", __name__)


@bp.get("/sem-list")
def sem_list():
    rows = get_sem_list()
    return jsonify(rows)
