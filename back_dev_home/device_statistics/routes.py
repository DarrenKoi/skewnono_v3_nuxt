from flask import Blueprint, jsonify, request

from .data import get_device_statistics

bp = Blueprint("device_statistics", __name__)


@bp.get("/device-statistics")
def device_statistics():
    fac_id_param = request.args.get("fac_id", "")
    fac_ids = [value.strip() for value in fac_id_param.split(",") if value.strip()]

    rows = get_device_statistics(fac_ids)
    return jsonify(rows)
