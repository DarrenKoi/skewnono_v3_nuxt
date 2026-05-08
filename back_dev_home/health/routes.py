from flask import Blueprint, jsonify

from back_dev_home.health.data import get_services_health

bp = Blueprint("health", __name__)


@bp.get("/health/services")
def services_health():
    return jsonify(get_services_health())
