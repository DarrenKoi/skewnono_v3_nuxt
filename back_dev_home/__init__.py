from flask import Flask
from flask_cors import CORS

from back_dev_home._core import bp as core_bp
from back_dev_home.afm import bp as afm_bp
from back_dev_home.device_statistics import bp as device_statistics_bp
from back_dev_home.sem_list import bp as sem_list_bp
from back_dev_home.storage import bp as storage_bp


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(afm_bp, url_prefix="/api")
    app.register_blueprint(core_bp, url_prefix="/api")
    app.register_blueprint(device_statistics_bp, url_prefix="/api")
    app.register_blueprint(sem_list_bp, url_prefix="/api")
    app.register_blueprint(storage_bp, url_prefix="/api")

    return app
