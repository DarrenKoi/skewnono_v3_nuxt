from flask import Blueprint

bp = Blueprint("core", __name__)


@bp.get("/health")
def health():
    return {"status": "ok"}
