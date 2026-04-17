from flask import Flask

from .api import api_bp
from .frontend import frontend_bp


def create_app() -> Flask:
  app = Flask(__name__)

  app.register_blueprint(api_bp)
  app.register_blueprint(frontend_bp)

  return app
