from flask import Flask
from flask_cors import CORS

from ._core import bp as core_bp
from .device_statistics import bp as device_statistics_bp
from .sem_list import bp as sem_list_bp


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(core_bp, url_prefix="/api")
    app.register_blueprint(device_statistics_bp, url_prefix="/api")
    app.register_blueprint(sem_list_bp, url_prefix="/api")

    return app
