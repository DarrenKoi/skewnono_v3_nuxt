from flask import Blueprint, jsonify

from ..config import FRONTEND_INDEX_FILE, FRONTEND_PUBLIC_ROOT

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.get('/health')
def health():
  return jsonify({
    'status': 'ok',
    'frontend_ready': FRONTEND_INDEX_FILE.exists(),
    'frontend_public_dir': str(FRONTEND_PUBLIC_ROOT)
  })
