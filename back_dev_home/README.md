# back_dev_home

Flask mock backend for Phase 1 (home / offline). Returns the same JSON shape as the office Flask server, but sources data from in-memory mock modules instead of OpenSearch/Redis.

## Setup

Run from the repo root:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r back_dev_home/requirements.txt
```

## Run

Direct (dev), from the repo root:

```bash
python index.py
```

Via WSGI (production-style): the repo-root `index.py` exposes `app` and `application` at module level and is imported by `wsgi.ini` as `module = index` + `callable = application`. `uwsgi --ini wsgi.ini` (or an equivalent `gunicorn index:application`) will serve the same Flask app.

Health check: `GET http://localhost:5000/api/health`

## Frontend integration

Run Nuxt with the proxy target pointing here:

```bash
cd ../front-dev-home
NUXT_API_TARGET=http://localhost:5000 npm run dev
```

Nitro proxies `/api/*` to Flask. The frontend composables are unchanged.

## Layout

```text
<repo-root>/
|-- index.py                     # WSGI entry (exposes app/application)
|-- wsgi.ini                     # uWSGI config (module=index, callable=application)
`-- back_dev_home/
    |-- __init__.py              # create_app() factory + feature registration
    |-- _core/                   # cross-feature infrastructure
    |   |-- __init__.py
    |   `-- routes.py            # GET /api/health
    |-- sem_list/                # feature: matches Nuxt tab
    |   |-- __init__.py          # re-exports `bp`
    |   |-- routes.py            # GET /api/sem-list
    |   `-- data.py              # Phase 1 mock; swap surface for Phase 2/3
    |-- requirements.txt
    `-- README.md
```

## Office migration (Phase 2)

Replace each feature's `data.py` (e.g. `sem_list/data.py`) with a module that queries OpenSearch / Redis. `routes.py` stays unchanged — it only consumes `get_sem_list()` etc. via `from .data import ...`, not the data source. Keep function signatures and return shapes stable.
