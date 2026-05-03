from flask import Blueprint, jsonify, request

from back_dev_home.device_statistics.data import get_device_desc, get_r3_device_grp
from back_dev_home.device_statistics.statistics import get_weekly_trend_data

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


@bp.get("/device-statistics/recipe-statistics")
def recipe_statistics():
    lot_cds_param = request.args.get("lot_cds", "")
    lot_cds = [value.strip() for value in lot_cds_param.split(",") if value.strip()]

    # NOTE: keep `points` at the default. `_seed_for(lot_cd, point_index)` in
    # statistics.py uses point_index, so reducing `points` shifts the index of
    # the "latest" date and changes the values for the same ISO date — the
    # deterministic-per-date guarantee documented in get_weekly_trend_data
    # breaks. The wasted dates are mock-data only and acceptable here.
    trend = get_weekly_trend_data(lot_cds or None)
    if not trend:
        return jsonify({"date": None, "buckets": {}})

    latest_date = next(reversed(trend))
    return jsonify({"date": latest_date, "buckets": trend[latest_date]})
