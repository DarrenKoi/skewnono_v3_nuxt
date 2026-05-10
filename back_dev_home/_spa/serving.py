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
                return send_from_directory(root_str, path)
            except NotFound:
                pass
        return send_from_directory(root_str, "index.html")
