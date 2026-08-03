from flask import Flask, abort, g, send_from_directory
from werkzeug.exceptions import NotFound

from .._runtime.env import spa_dir

# Set on `g` when this mount answers with a real file out of the build dir.
# `_logging/activity.py` reads it to skip logging asset traffic, and spells the
# name literally rather than importing it, so `create_app` can keep deferring
# this module's import behind `is_cloud()`. A test pins the two spellings.
STATIC_FILE_FLAG = "_spa_static_file"


def register_spa(app: Flask) -> None:
    root = spa_dir()
    if not root.is_dir():
        app.logger.warning("SPA dir missing at %s; skipping SPA mount", root)
        return

    root_str = str(root)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path: str):
        if path.startswith("api/"):
            abort(404)
        if path:
            try:
                resp = send_from_directory(root_str, path)
            except NotFound:
                pass
            else:
                setattr(g, STATIC_FILE_FLAG, True)
                # Nuxt content-hashes everything under _nuxt/, so those files
                # never change in place — cache hard. index.html and other
                # public/ assets keep Flask's default conditional (ETag)
                # caching so a fresh deploy is picked up on the next request.
                if path.startswith("_nuxt/"):
                    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                # Icons and fonts are the exception to the conditional rule:
                # Chrome re-resolves the page icon on history navigations, and
                # the SPA rewrites the URL on every parameter click — under
                # no-cache that means a favicon revalidation per click (and,
                # when the backend is unhealthy, a retry cascade across every
                # declared icon). A day of staleness is fine for both.
                elif path.startswith(("favicon/", "fonts/")) or path == "favicon.ico":
                    resp.headers["Cache-Control"] = "public, max-age=86400"
                return resp
        return send_from_directory(root_str, "index.html")
