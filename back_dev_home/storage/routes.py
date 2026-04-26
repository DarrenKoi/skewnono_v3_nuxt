from flask import Blueprint, jsonify, request

from .data import get_storage

bp = Blueprint("storage", __name__)


@bp.get("/storage")
def storage():
    fac_id_param = request.args.get("fac_id", "")
    fac_ids = [value.strip() for value in fac_id_param.split(",") if value.strip()]

    rows = get_storage(fac_ids)
    return jsonify(rows)
