import importlib
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, g, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from ._auth.errors import error_json
from ._auth.middleware import install_identity_middleware
from ._auth.provider import ANONYMOUS, CloudIdentityProvider, LocalIdentityProvider
from ._logging.activity import install_activity_logging
from ._runtime.boot import log_provider_table
from ._runtime.data_provider import get_mode, validate_env
from ._runtime.env import is_cloud


def _rate_limit_key() -> str:
    # Every cookie-less cloud caller shares the literal `anonymous` id, so
    # keying on it would pool the whole fab into ONE 20-req budget the day a
    # proxy config strips LASTUSER — turning that quiet misconfiguration into
    # a site-wide 429 storm. Those callers get per-address buckets instead
    # (real addresses once SKEWNONO_TRUST_PROXY is on behind nginx).
    user_id = getattr(g, "user_id", None)
    if user_id == ANONYMOUS:
        return f"anon:{request.remote_addr or 'unknown'}"
    return user_id or request.remote_addr or "anon"


def _rate_limit_storage() -> dict:
    """Limiter storage kwargs: in-process at home, shared Redis at the office.

    memory:// counters are per-process, which under Phase 3's multi-worker
    uwsgi turns "20 per 5 seconds" into "20 per worker, nondeterministically"
    — and lets a client rotating cookie values mint a fresh bucket per worker
    it happens to hit. Office mode points the limiter at the Redis the
    adapters already use; an unreachable Redis degrades to the per-worker
    memory fallback rather than failing requests.
    """
    host = os.environ.get("REDIS_HOST")
    if get_mode() != "office" or not host:
        return {"storage_uri": "memory://"}
    from urllib.parse import quote

    password = os.environ.get("REDIS_PASSWORD")
    auth = f":{quote(password, safe='')}@" if password else ""
    port = os.environ.get("REDIS_PORT", "6379")
    return {
        "storage_uri": f"redis://{auth}{host}:{port}/0",
        # Bound the probe: a host that drops SYNs must cost ~1s once on the
        # way to the fallback, not stall every request on client defaults.
        "storage_options": {"socket_connect_timeout": 1, "socket_timeout": 1},
        "in_memory_fallback_enabled": True,
    }


def _install_rate_limit(app: Flask) -> None:
    from flask_limiter import Limiter

    # 5/5s was so tight that any page mounting 2+ composables + a user pill
    # click would 429. 20/5s still catches runaway loops but tolerates
    # normal interactive navigation.
    #
    # application_limits, not default_limits: one budget per user shared
    # across ALL /api routes, which is the contract CLAUDE.md documents.
    # default_limits would give each route its own 20/5s window — a runaway
    # loop rotating across N endpoints would run at N×20 req/5s and never
    # 429 — and would leave application_limits_exempt_when inert (it only
    # applies to application limits).
    limiter = Limiter(
        key_func=_rate_limit_key,
        application_limits=["20 per 5 seconds"],
        application_limits_exempt_when=lambda: not request.path.startswith("/api/"),
        **_rate_limit_storage(),
    )
    limiter.init_app(app)

    # Exempt non-API endpoints (SPA catch-all, /login) so SPA bundle loads and
    # the SSO bootstrap aren't counted toward the per-user API budget.
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/api/"):
            continue
        view = app.view_functions.get(rule.endpoint)
        if view is not None:
            limiter.exempt(view)

    # SEM image serving fans out dozens of <img>/list requests per gallery view;
    # exempt the whole msr_image blueprint from the per-user API budget.
    for endpoint, view in app.view_functions.items():
        if endpoint.startswith("msr_image."):
            limiter.exempt(view)


def _install_json_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def _json_http_error(err: HTTPException):
        code = (err.name or "error").lower().replace(" ", "_")
        message = err.description or err.name or "error"
        return error_json(code, message, err.code or 500)

    # Office adapters fail loudly on backing-store trouble: bare LookupError
    # for a missing Redis key / OpenSearch alias, bare RuntimeError for unset
    # env config. Without handlers those land as opaque HTML 500 tracebacks;
    # map them to JSON 502 (bad upstream data) / 503 (backend unconfigured or
    # unreachable) so the SPA can show the message. Only the *exact* base
    # types are adapter signals — subclasses (KeyError, NotImplementedError,
    # ...) are programming bugs and must stay real 500s.
    def _internal_500(err: Exception):
        app.logger.exception("unhandled error")
        return error_json("internal_server_error", "internal server error", 500)

    @app.errorhandler(LookupError)
    def _json_upstream_data_error(err: LookupError):
        if type(err) is not LookupError:
            return _internal_500(err)
        app.logger.exception("upstream data error")
        return error_json("upstream_data_error", str(err) or "upstream data error", 502)

    @app.errorhandler(RuntimeError)
    def _json_backend_config_error(err: RuntimeError):
        if type(err) is not RuntimeError:
            return _internal_500(err)
        app.logger.exception("backend configuration error")
        return error_json("backend_unavailable", str(err) or "backend unavailable", 503)

    # Driver-specific connection failures (redis/opensearch do NOT subclass
    # the builtin ConnectionError). Imported lazily: the drivers are only
    # required where office providers run.
    try:
        from redis.exceptions import ConnectionError as RedisConnectionError
        from redis.exceptions import TimeoutError as RedisTimeoutError

        @app.errorhandler(RedisConnectionError)
        def _json_redis_conn_error(err: Exception):
            app.logger.exception("redis connection error")
            return error_json("backend_unreachable", str(err) or "Redis unreachable", 503)

        @app.errorhandler(RedisTimeoutError)
        def _json_redis_timeout_error(err: Exception):
            app.logger.exception("redis timeout")
            return error_json("backend_unreachable", str(err) or "Redis timeout", 503)
    except ImportError:
        pass

    try:
        from opensearchpy.exceptions import ConnectionError as OSConnectionError

        @app.errorhandler(OSConnectionError)
        def _json_opensearch_conn_error(err: Exception):
            app.logger.exception("opensearch connection error")
            return error_json(
                "backend_unreachable", str(err) or "OpenSearch unreachable", 503
            )
    except ImportError:
        pass


def create_app() -> Flask:
    load_dotenv(Path(__file__).parent / ".env")
    # static_folder=None: Flask otherwise registers /static/<filename> against
    # back_dev_home/static/, a directory that does not exist. That rule is more
    # specific than the SPA catch-all, so in Phase 3 anything the SPA shipped
    # under /static/ answered 404 while the real file sat unread in the build.
    # Nothing collides today; the SPA owns every non-/api path, so the mount in
    # _spa/serving.py should be the only thing claiming them.
    app = Flask(__name__, static_folder=None)

    # The declared identity (`_auth/self_id.py`) rides in a signed session
    # cookie, and its `verified` flag is only a claim the signature makes
    # credible. A default key is a public constant in this repository, so on
    # the cloud a missing value is not a weak configuration — it is an unsigned
    # session that still looks signed, with no error to notice. Refuse to start
    # instead: the failure then appears once, at deploy, rather than never.
    #
    # The gate asks whether a value was CHOSEN, not whether it is strong.
    # Judging strength here would block a deploy over a policy this code has no
    # standing to set. A blank counts as absent — `SKEWNONO_SECRET_KEY=` in a
    # .env reads as "", which a plain presence check would wave through.
    secret = (os.environ.get("SKEWNONO_SECRET_KEY") or "").strip()
    if not secret:
        if is_cloud():
            raise RuntimeError(
                "SKEWNONO_SECRET_KEY is required on the cloud: it signs the "
                "self-identification session, whose `verified` flag is "
                "forgeable without it. Set any non-empty value in "
                "/project/workSpace/back_dev_home/.env and restart."
            )
        secret = "dev-only-not-for-prod"
    app.secret_key = secret

    # Only sessions marked permanent get a lifetime, and `self_id`'s writer
    # marks them — setting this without that would leave it inert and every
    # declaration would evaporate when the tab closed.
    app.permanent_session_lifetime = timedelta(days=30)

    # Explicit rather than inherited from browser defaults: without SameSite,
    # a browser still on pre-Lax-by-default behavior sends the session cookie
    # on a cross-site form POST, and /api/identify's response *plants* an
    # attacker-chosen declared identity — login-CSRF whose payoff is 30 days
    # of mis-attributed activity. Lax keeps deep links working (top-level
    # navigations carry the cookie) while refusing the cross-site POST.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Config must agree with the filesystem before we serve anything: an
    # explicit SKEWNONO_<FEATURE>_PROVIDER=office with no providers/office.py
    # is a promise of real fab data we cannot keep, so refuse to start rather
    # than answer it with mock at 2am. Then record what actually resolved —
    # presence detection leaves no .env line to read afterwards.
    validate_env()
    log_provider_table()

    CORS(
        app,
        resources={r"/api/*": {"origins": ["http://localhost:3100"]}},
        supports_credentials=True,
    )

    _install_json_error_handlers(app)

    provider = CloudIdentityProvider() if is_cloud() else LocalIdentityProvider()
    install_identity_middleware(app, provider)
    install_activity_logging(app)

    # wsgi.ini exposes http-socket directly today, so request.remote_addr is
    # already the real client IP and trusting X-Forwarded-For would let any
    # caller forge their own address with a header. But wsgi.ini:20-24
    # documents the nginx move, and making it would silently record every
    # request as 127.0.0.1 with no error at all — including the declared_from
    # that self-identification exists to capture.
    #
    # Opt-in, so the trust is a deployment decision rather than something this
    # code guesses. Parsed against a list of true-ish spellings: treating any
    # non-empty string as true is how `=false` turns an opt-in into always-on.
    if (os.environ.get("SKEWNONO_TRUST_PROXY") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        from werkzeug.middleware.proxy_fix import ProxyFix

        # x_for ONLY. The spec asks for this to fix the client IP, and the
        # other headers are not free: trusting X-Forwarded-Proto on a
        # deployment that is deliberately http-only (skewnono.skhynix.com) would
        # let a proxy header flip url_for() to https and break every generated
        # link, and X-Forwarded-Host would do the same to the hostname.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    # Demo users are fabricated, so they must never reach a process serving
    # office data. is_cloud() alone only rules out Phase 3 — Phase 2 runs on
    # office localhost, where the filesystem looks like home, so the seeding
    # ran there and any feature falling back to the mock adapter would show
    # five invented employees as real ones. Both conditions are needed: the
    # SKEWNONO_DATA_PROVIDER=mock kill switch makes get_mode() report "mock"
    # even on the cloud host.
    if get_mode() == "mock" and not is_cloud():
        from .activity.data import seed_demo_users
        seed_demo_users()

    package_root = Path(__file__).parent
    for routes_file in sorted(package_root.rglob("routes.py")):
        rel_parts = routes_file.relative_to(package_root).parts[:-1]
        if any(part.startswith("_") for part in rel_parts):
            continue
        module_path = ".".join((__name__, *rel_parts))
        module = importlib.import_module(module_path)
        bp = getattr(module, "bp", None)
        if not isinstance(bp, Blueprint):
            raise RuntimeError(
                f"{module_path} has routes.py but does not export a Blueprint named 'bp'"
            )
        app.register_blueprint(bp, url_prefix="/api")

    # Identity exists in every phase, so /api/me does too — a home session that
    # could not answer it would develop against a screen the cloud never shows.
    # Registered by hand because the factory's rglob skips _-prefixed folders.
    from ._auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api")

    if is_cloud():
        from ._spa.serving import register_spa
        register_spa(app)

    _install_rate_limit(app)

    from ._scheduler import start_scheduler
    start_scheduler(app)

    return app
