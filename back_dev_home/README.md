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
    |-- afm/                     # tool family: AFM (single-tier feature)
    |   |-- __init__.py
    |   |-- routes.py
    |   `-- data.py
    |-- ebeam/                   # tool family: groups all e-beam tools
    |   |-- __init__.py          # namespace only — no Blueprint
    |   |-- cdsem/               # tool: CD-SEM (namespace; sub-features below)
    |   |   |-- __init__.py      # namespace only — no Blueprint
    |   |   |-- storage/         # feature: per-tool storage inventory
    |   |   |   |-- __init__.py  # re-exports `bp`
    |   |   |   |-- routes.py    # Blueprint("cdsem_storage") — /api/cdsem/storage*
    |   |   |   `-- data.py      # Phase 1 mock; swap surface for Phase 2/3
    |   |   `-- device_statistics/   # feature: recipe + device stats (CD-SEM only)
    |   |       |-- __init__.py      # re-exports `bp`
    |   |       |-- routes.py        # Blueprint("cdsem_device_statistics") — /api/cdsem/device-statistics/*
    |   |       |-- data.py
    |   |       `-- statistics.py
    |   `-- hvsem/               # tool: HV-SEM (namespace; sub-features below)
    |       |-- __init__.py      # namespace only — no Blueprint
    |       `-- storage/         # feature: per-tool storage inventory
    |           |-- __init__.py  # re-exports `bp`
    |           |-- routes.py    # Blueprint("hvsem_storage") — /api/hvsem/storage*
    |           `-- data.py      # currently identical to cdsem; differentiate later
    |-- sem_list/                # feature: cross-tool SEM list
    |   |-- __init__.py          # re-exports `bp`
    |   |-- routes.py            # GET /api/sem-list
    |   `-- data.py              # Phase 1 mock; swap surface for Phase 2/3
    |-- requirements.txt
    `-- README.md
```

## Office migration (Phase 2)

Replace each feature's `data.py` (e.g. `sem_list/data.py`, `ebeam/cdsem/storage/data.py`) with a module that queries OpenSearch / Redis. `routes.py` stays unchanged — it only consumes `get_sem_list()` etc. via `from .data import ...`, not the data source. Keep function signatures and return shapes stable.

## Adding a new e-beam tool feature

The `ebeam/<tool>/` folders are **namespaces**, not Blueprints — each sub-feature folder (e.g. `ebeam/cdsem/storage/`) is its own Blueprint. To add a new feature for an existing tool:

1. Create `back_dev_home/ebeam/<tool>/<feature>/` with `__init__.py`, `routes.py`, `data.py`.
2. In `routes.py`, declare `bp = Blueprint("<tool>_<feature>", __name__)` — the prefix keeps Blueprint names globally unique.
3. URL paths inside `routes.py` should be prefixed with `/<tool>/...` so the namespace is reflected in the URL too.
4. Register the new Blueprint in `back_dev_home/__init__.py` under `create_app()`.
