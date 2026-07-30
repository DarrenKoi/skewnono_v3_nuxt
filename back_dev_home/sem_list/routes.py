from flask import Blueprint, jsonify

from back_dev_home.sem_list.data import get_pending_tools, get_sem_list

bp = Blueprint("sem_list", __name__)


@bp.get("/sem-list")
def sem_list():
    rows = get_sem_list()
    return jsonify(rows)


@bp.get("/sem-list/pending")
def sem_list_pending():
    """Roster tools skewnono cannot reach yet — the firewall-request queue.

    Separate from /sem-list because that response is the fleet identity
    source six other features join through; adding unreachable tools there
    would put them in every tool picker in the app.
    """
    rows = get_pending_tools()
    return jsonify(rows)
