import importlib
import os
from pathlib import Path

from flask import Blueprint, Flask, g, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from ._auth.errors import error_json
from ._auth.middleware import install_identity_middleware
from ._auth.provider import CloudIdentityProvider, LocalIdentityProvider
from ._logging.activity import install_activity_logging
from ._runtime.env import is_cloud


def _rate_limit_key() -> str:
    return getattr(g, "user_id", None) or request.remote_addr or "anon"


def _install_rate_limit(app: Flask) -> None:
    from flask_limiter import Limiter

    limiter = Limiter(
        key_func=_rate_limit_key,
        storage_uri="memory://",
        default_limits=["1 per 2 seconds"],
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


def _install_json_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def _json_http_error(err: HTTPException):
        code = (err.name or "error").lower().replace(" ", "_")
        message = err.description or err.name or "error"
        return error_json(code, message, err.code or 500)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SKEWNONO_SECRET_KEY", "dev-only-not-for-prod")

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

    if is_cloud():
        from ._auth.routes import bp as auth_bp
        app.register_blueprint(auth_bp)

        from ._spa.serving import register_spa
        register_spa(app)

    _install_rate_limit(app)

    return app
