from flask import Flask
from flask_cors import CORS

from back_dev_home._core import bp as core_bp
from back_dev_home.afm import bp as afm_bp
from back_dev_home.announcements import bp as announcements_bp
from back_dev_home.ebeam.cdsem.device_statistics import bp as cdsem_device_statistics_bp
from back_dev_home.ebeam.cdsem.storage import bp as cdsem_storage_bp
from back_dev_home.ebeam.hvsem.storage import bp as hvsem_storage_bp
from back_dev_home.ebeam.recipe_search import bp as recipe_search_bp
from back_dev_home.ebeam.recipe_tat import bp as recipe_tat_bp
from back_dev_home.health import bp as health_bp
from back_dev_home.sem_list import bp as sem_list_bp


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(afm_bp, url_prefix="/api")
    app.register_blueprint(announcements_bp, url_prefix="/api")
    app.register_blueprint(cdsem_device_statistics_bp, url_prefix="/api")
    app.register_blueprint(cdsem_storage_bp, url_prefix="/api")
    app.register_blueprint(core_bp, url_prefix="/api")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(hvsem_storage_bp, url_prefix="/api")
    app.register_blueprint(recipe_search_bp, url_prefix="/api")
    app.register_blueprint(recipe_tat_bp, url_prefix="/api")
    app.register_blueprint(sem_list_bp, url_prefix="/api")

    return app
