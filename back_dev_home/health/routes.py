import logging

from flask import Blueprint, current_app, jsonify, request

from back_dev_home._auth.admin import require_admin
from back_dev_home._auth.errors import error_json
from back_dev_home._logging.opensearch_handler import installed_handler
from back_dev_home._runtime.data_provider import get_mode, resolve_all
from back_dev_home._runtime.site import detect_site
from back_dev_home.health.data import get_services_health

bp = Blueprint("health", __name__)
logger = logging.getLogger("skewnono.health")


@bp.get("/health/services")
def services_health():
    """The landing page's health card. Open to every user on purpose.

    No auth gate: a normal user seeing "Redis is down" is the whole point of
    the card, and the rows carry no internal detail — each probe's failure
    text is the exception class only (see providers/probe_common.py).
    """
    try:
        return jsonify(get_services_health())
    except Exception:
        # Each probe traps its own exceptions, so reaching here means the
        # provider itself broke (a bad office.py import, a config raise), not
        # that a service is down. Answer the JSON envelope the rest of /api
        # uses instead of Flask's bare HTML 500, and keep the shape contract
        # honest: on failure there is no `services` array at all rather than a
        # short one.
        logger.exception("health provider failed outside the per-probe traps")
        return error_json(
            "health_unavailable",
            "Could not collect service health",
            503,
        )


@bp.get("/health/providers")
@require_admin
def providers_health():
    """Which features are serving office data right now, and why.

    Reads the runtime directly rather than going through health/data.py: this
    is introspection, not phase-swappable data, and a swappable version could
    misreport itself in exactly the situation you would query it.

    Admin-only: the table names every backend feature and the reason each
    resolved the way it did — deployment shape, not something a normal user
    has any use for.
    """
    return jsonify(
        {
            "site": detect_site() or "unknown",
            "mode": get_mode(),
            "features": [row._asdict() for row in resolve_all()],
        }
    )


@bp.get("/health/logging")
@require_admin
def logging_health():
    """Delivery diagnostics for the OpenSearch log shipper.

    Same introspection carve-out as /health/providers: reads the installed
    handler directly. The shipper drops documents rather than fail requests,
    so without this endpoint sustained loss only shows up as quietly shrinking
    activity metrics.

    Admin-only: it names the log index alias and the deployment, and its
    counters are an operator's signal rather than a user's.
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


_DEFAULT_JOB_LIMIT = 200


@bp.get("/health/jobs")
@require_admin
def jobs_health():
    """Recent scheduler run records — start, end, error, skip, missed.

    Same introspection carve-out as /health/providers: reads the run log off
    the app rather than going through a provider. Admin-only because it names
    internal job ids and their timings.

    The retention cap lives in the storage layer (memory ring buffer at home, a
    Redis LTRIM at the office), so the ceiling below is read from the config
    rather than duplicated here. A worker that never elected still answers:
    at the office every worker reads the same Redis list.
    """
    from back_dev_home._scheduler.config import load_scheduler_config

    ceiling = load_scheduler_config().log_list_max
    raw_limit = request.args.get("limit", "")
    try:
        limit = int(raw_limit) if raw_limit else _DEFAULT_JOB_LIMIT
    except ValueError:
        limit = _DEFAULT_JOB_LIMIT
    limit = max(1, min(limit, ceiling))

    run_log = current_app.extensions.get("scheduler_run_log")
    records = run_log.read(limit) if run_log is not None else []
    return jsonify({"limit": limit, "records": records})
