import logging

from flask import Blueprint, current_app, jsonify, request

from back_dev_home._auth.admin import require_admin
from back_dev_home._auth.errors import error_json
from back_dev_home._logging.opensearch_handler import installed_handler
from back_dev_home._runtime.data_provider import get_data_provider, get_mode, resolve_all
from back_dev_home._runtime.env import is_cloud
from back_dev_home._runtime.office_registry import features
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


@bp.get("/health/deployment")
def deployment():
    """Is this the Phase 3 cloud instance?

    Open to every user, and the narrowest possible slice of what its
    admin-only sibling /health/providers reports. The gate there is about
    naming every feature and the reason each resolved; this answers only
    "which deployment am I talking to", which the caller already knows from
    the address bar. There is nothing here to withhold.

    Exists because the SPA cannot answer it alone: `ssr: false` bakes
    `runtimeConfig.public` at build time, and the artifact built at the office
    is the same one that ships to the cloud, so a build-time flag would have
    to be remembered on every pack. The frontend uses this to keep 실험실
    entries whose page is not validated yet out of the production menu — see
    `useDeployment.ts`. Hiding the MENU only: the routes stay reachable for
    anyone holding the URL, which is deliberate (power users, beta testers).

    `is_cloud()` rather than `detect_site()`: Phase 2 at the office runs on a
    company localhost and SHOULD show the unvalidated pages, because that is
    where they get exercised against real data. Only the cloud deploy hides
    them, and is_cloud() is a filesystem-path check (`_runtime/env.py`), so
    it cannot be flipped by a stray environment variable.
    """
    return jsonify({"is_cloud": is_cloud()})


@bp.get("/health/data-mode")
def data_mode():
    """Is ONE named feature serving generated data right now?

    Open to every user, unlike its sibling /health/providers, and the split is
    the reason both exist. The providers table enumerates every backend feature
    with the deployment reason each resolved the way it did — that is admin
    material. This answers a single question about a single feature the caller
    already names, and the answer is something a user reading a chart is
    entitled to: whether the numbers in front of them came out of a generator.

    The frontend needs it because a home mock can fabricate a relationship that
    does not exist in the fab — CD and FDC are both biased by one per-MSR
    `health` scalar, so their correlation is an artifact of the generator (see
    docs/issues/skewvoir/analysis-drilldown-benchmark-research.md §7.3). A
    screen that draws that correlation has to say so, and it cannot say so
    behind an admin gate.

    Unknown feature is a 404 rather than a default: answering "mock" for a typo
    would paint a demo warning over real data, and answering "office" would
    hide one over generated data. Both are worse than no answer.
    """
    feature = (request.args.get("feature") or "").strip()
    if not feature:
        return error_json("bad_request", "feature query param is required")
    if feature not in features():
        return error_json("not_found", f"unknown feature: {feature}", 404)

    return jsonify({"feature": feature, "provider": get_data_provider(feature)})


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
