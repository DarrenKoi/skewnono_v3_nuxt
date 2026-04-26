from flask import Blueprint, jsonify, request

from .data import get_device_desc, get_r3_device_grp

bp = Blueprint("device_statistics", __name__)


@bp.get("/device-statistics/r3-device-grp")
def r3_device_grp():
    return jsonify(get_r3_device_grp())


@bp.get("/device-statistics/device-desc")
def device_desc():
    fac_id_param = request.args.get("fac_id", "")
    fac_ids = [value.strip() for value in fac_id_param.split(",") if value.strip()]

    rows = get_device_desc(fac_ids)
    return jsonify(rows)
