# Flask + Nuxt `.output` integration

This Flask app uses a blueprint-first structure so API endpoints can grow without turning `app.py` into a monolith.

## Package layout

```text
flask_api/
├── __init__.py
├── app.py
├── config.py
├── factory.py
├── api/
│   ├── __init__.py
│   └── routes.py
├── frontend/
│   ├── __init__.py
│   └── routes.py
└── requirements.txt
```

## Structure notes

- `factory.py` creates the Flask app and registers blueprints.
- `api/routes.py` owns backend endpoints under `/api/*`.
- `frontend/routes.py` owns static file serving and SPA fallback behavior for Nuxt.
- `config.py` keeps shared path configuration in one place.
- `app.py` is only the local run entrypoint.

## 1. Generate the Nuxt static files

Run this from the repo root:

```bash
cd front-dev-home
npm run generate
```

That command creates route HTML and assets under `.output/public`, which Flask can serve directly.

## 2. Install Flask

```bash
cd flask_api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Run the server

From the repo root:

```bash
flask --app flask_api run --debug
```

Or:

```bash
python3 -m flask_api.app
```

## 4. Request flow

- `/api/*` stays in Flask for backend endpoints.
- Static files like `/_nuxt/*`, `/favicon.ico`, and prerendered pages are served from `front-dev-home/.output/public`.
- Any other non-API route falls back to `index.html` so the Nuxt client router can handle it.

## 5. Development mode

While Nuxt is running in dev mode, point its proxy to Flask:

```bash
cd front-dev-home
NUXT_API_TARGET=http://127.0.0.1:5000 npm run dev
```

Then frontend calls to `/api/...` are proxied to Flask, while production can be served by Flask from the generated `.output/public` directory.
