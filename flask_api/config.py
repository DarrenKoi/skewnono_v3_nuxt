from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_PUBLIC_ROOT = (ROOT_DIR / 'front-dev-home' / '.output' / 'public').resolve()
FRONTEND_INDEX_FILE = FRONTEND_PUBLIC_ROOT / 'index.html'
