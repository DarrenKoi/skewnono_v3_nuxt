from flask import Blueprint, abort, jsonify, request

from back_dev_home.ebeam.device_statistics.data import (
    get_device_desc,
    get_meas_activity,
    get_r3_device_grp,
    get_recipe_params,
    get_rules,
    get_weekly_trend_data,
)

bp = Blueprint("device_statistics", __name__)


@bp.get("/cdsem/device-statistics/r3-device-grp")
def r3_device_grp():
    return jsonify(get_r3_device_grp())


@bp.get("/cdsem/device-statistics/device-desc")
def device_desc():
    fac_id_param = request.args.get("fac_id", "")
    fac_ids = [value.strip() for value in fac_id_param.split(",") if value.strip()]

    rows = get_device_desc(fac_ids)
    return jsonify(rows)


@bp.get("/cdsem/device-statistics/meas-activity")
def meas_activity():
    # lot_cd 별 최근 90일 측정 건수 순위 (meas_count 내림차순). 빠른 필터의
    # "측정 상위 N" 이 소비합니다. fab 축이 없으면 순위가 의미를 잃으므로
    # fac_id 는 필수입니다 (rules 와 같은 방침).
    fac_id = request.args.get("fac_id", "").strip()
    if not fac_id:
        abort(400, description="fac_id query parameter is required")

    return jsonify(get_meas_activity(fac_id))


@bp.get("/cdsem/device-statistics/recipe-statistics")
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


@bp.get("/cdsem/device-statistics/recipe-params")
def recipe_params():
    lot_cds_param = request.args.get("lot_cds", "")
    lot_cds = [value.strip() for value in lot_cds_param.split(",") if value.strip()]
    return jsonify(get_recipe_params(lot_cds or None))


@bp.get("/cdsem/device-statistics/rules")
def measurement_rules():
    # Current rule version for a fab (D8/D15 seed). The frontend ruleEngine
    # consumes these cells client-side; this endpoint ships raw rules only.
    fac_id = request.args.get("fac_id", "").strip()
    if not fac_id:
        abort(400, description="fac_id query parameter is required")

    rules = get_rules(fac_id)
    if rules is None:
        abort(404, description=f"no rules for fac_id '{fac_id}'")

    return jsonify(rules)


@bp.get("/cdsem/device-statistics/recipe-trend")
def recipe_trend():
    lot_cds_param = request.args.get("lot_cds", "")
    lot_cds = [value.strip() for value in lot_cds_param.split(",") if value.strip()]
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None

    # Same `points`-stability constraint as recipe_statistics: always
    # generate the full window, then slice by date string. ISO YYYY-MM-DD
    # is lexicographically sortable so direct >=/<= comparisons work.
    # Trend chart only consumes *_summary buckets, so skip rcp_info to
    # avoid serializing thousands of unused recipe rows.
    full = get_weekly_trend_data(lot_cds or None, include_recipes=False)

    dates = [
        d for d in full.keys()
        if (start_date is None or d >= start_date)
        and (end_date is None or d <= end_date)
    ]
    trend = {d: full[d] for d in dates}
    return jsonify({"dates": dates, "trend": trend})
