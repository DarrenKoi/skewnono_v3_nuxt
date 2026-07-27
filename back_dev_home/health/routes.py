from flask import Blueprint, jsonify

from back_dev_home._logging.opensearch_handler import installed_handler
from back_dev_home._runtime.data_provider import get_mode, resolve_all
from back_dev_home._runtime.site import detect_site
from back_dev_home.health.data import get_services_health

bp = Blueprint("health", __name__)


@bp.get("/health/services")
def services_health():
    return jsonify(get_services_health())


@bp.get("/health/providers")
def providers_health():
    """Which features are serving office data right now, and why.

    Reads the runtime directly rather than going through health/data.py: this
    is introspection, not phase-swappable data, and a swappable version could
    misreport itself in exactly the situation you would query it.
    """
    return jsonify(
        {
            "site": detect_site() or "unknown",
            "mode": get_mode(),
            "features": [row._asdict() for row in resolve_all()],
        }
    )


@bp.get("/health/logging")
def logging_health():
    """Delivery diagnostics for the OpenSearch log shipper.

    Same introspection carve-out as /health/providers: reads the installed
    handler directly. The shipper drops documents rather than fail requests,
    so without this endpoint sustained loss only shows up as quietly shrinking
    activity metrics.
    """
    handler = installed_handler()
    if handler is None:
        return jsonify(
            {
                "installed": False,
                "target": None,
                "diagnostics": None,
            }
        )
    return jsonify(
        {
            "installed": True,
            "target": {
                "alias": handler.index,
                "deployment": handler.deployment,
            },
            "diagnostics": handler.snapshot().as_dict(),
        }
    )
