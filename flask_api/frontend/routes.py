from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, jsonify, send_from_directory

from ..config import FRONTEND_INDEX_FILE, FRONTEND_PUBLIC_ROOT

frontend_bp = Blueprint('frontend', __name__)


def resolve_public_path(request_path: str) -> Path | None:
  candidate = (FRONTEND_PUBLIC_ROOT / request_path).resolve()

  try:
    candidate.relative_to(FRONTEND_PUBLIC_ROOT)
  except ValueError:
    return None

  return candidate


def frontend_missing_response():
  return (
    jsonify({
      'error': 'Nuxt static build not found.',
      'expected_file': str(FRONTEND_INDEX_FILE),
      'build_command': 'cd front-dev-home && npm run generate'
    }),
    503
  )


def send_public_file(path: Path):
  relative_path = path.relative_to(FRONTEND_PUBLIC_ROOT).as_posix()
  return send_from_directory(FRONTEND_PUBLIC_ROOT, relative_path)


@frontend_bp.route('/', defaults={'path': ''})
@frontend_bp.route('/<path:path>')
def serve_frontend(path: str):
  if path.startswith('api/'):
    abort(404)

  if not FRONTEND_INDEX_FILE.exists():
    return frontend_missing_response()

  if path:
    direct_file = resolve_public_path(path)
    if direct_file and direct_file.is_file():
      return send_public_file(direct_file)

    nested_index = resolve_public_path(f'{path}/index.html')
    if nested_index and nested_index.is_file():
      return send_public_file(nested_index)

    html_file = resolve_public_path(f'{path}.html')
    if html_file and html_file.is_file():
      return send_public_file(html_file)

  return send_public_file(FRONTEND_INDEX_FILE)
