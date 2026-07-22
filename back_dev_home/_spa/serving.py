from flask import Flask, abort, send_from_directory
from werkzeug.exceptions import NotFound

from .._runtime.env import spa_dir


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
                # Nuxt content-hashes everything under _nuxt/, so those files
                # never change in place — cache hard. index.html and public/
                # assets keep Flask's default conditional (ETag) caching so a
                # fresh deploy is picked up on the next request.
                if path.startswith("_nuxt/"):
                    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                return resp
        return send_from_directory(root_str, "index.html")
