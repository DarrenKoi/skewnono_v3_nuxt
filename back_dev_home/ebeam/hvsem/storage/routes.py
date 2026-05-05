from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.hvsem.storage.data import get_storage, get_storage_unavailable

bp = Blueprint("hvsem_storage", __name__)


def _parse_fac_ids() -> list[str]:
    fac_id_param = request.args.get("fac_id", "")
    return [value.strip() for value in fac_id_param.split(",") if value.strip()]


@bp.get("/hvsem/storage")
def storage():
    rows = get_storage(_parse_fac_ids())
    return jsonify(rows)


@bp.get("/hvsem/storage-unavailable")
def storage_unavailable():
    rows = get_storage_unavailable(_parse_fac_ids())
    return jsonify(rows)
