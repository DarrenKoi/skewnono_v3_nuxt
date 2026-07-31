import importlib
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, g, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from ._auth.errors import error_json
from ._auth.middleware import install_identity_middleware
from ._auth.provider import CloudIdentityProvider, LocalIdentityProvider
from ._logging.activity import install_activity_logging
from ._runtime.boot import log_provider_table
from ._runtime.data_provider import validate_env
from ._runtime.env import is_cloud


def _rate_limit_key() -> str:
    return getattr(g, "user_id", None) or request.remote_addr or "anon"


def _install_rate_limit(app: Flask) -> None:
    from flask_limiter import Limiter

    # 5/5s was so tight that any page mounting 2+ composables + a user pill
    # click would 429. 20/5s still catches runaway loops but tolerates
    # normal interactive navigation.
    limiter = Limiter(
        key_func=_rate_limit_key,
        storage_uri="memory://",
        default_limits=["20 per 5 seconds"],
        application_limits_exempt_when=lambda: not request.path.startswith("/api/"),
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
    app.secret_key = os.environ.get("SKEWNONO_SECRET_KEY", "dev-only-not-for-prod")

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

    if not is_cloud():
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

    from back_dev_home.msr_image.scheduler import start_purge_scheduler
    start_purge_scheduler(app)

    return app
