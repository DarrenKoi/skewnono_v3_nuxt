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

Health check: `GET http://localhost:5000/api/health/services`

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
    |-- health/                  # backend dependency health status
    |   |-- __init__.py
    |   |-- routes.py            # GET /api/health/services
    |   `-- data.py
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
    |   |       |-- routes.py        # Blueprint("device_statistics") — /api/cdsem/device-statistics/*
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

Provider-backed features keep `routes.py` and `data.py` unchanged. Implement the
real source in the feature's `providers/office.py`, normalize its result to
`contracts.py`, then select it with `SKEWNONO_DATA_PROVIDER=office` or a feature
override. For storage, use `SKEWNONO_STORAGE_PROVIDER=office`; this selects the
office adapter for both `/api/<tool_slug>/storage` and
`/api/<tool_slug>/ppid-unavailable`. Keep the function interfaces and response
shapes stable.

## Adding a new e-beam tool feature

The `ebeam/` layer has three kinds of folders:

- `ebeam/hitachi/<feature>/` — features shared across CD-SEM and HV-SEM (Hitachi tool family). Routes use Flask's `<tool_slug>` URL converter and produce both `/api/cdsem/<feature>/...` and `/api/hvsem/<feature>/...` endpoints from a single source of truth. Per-tool constants live in `ebeam/hitachi/_tool_specs.py`.
- `ebeam/cdsem/<feature>/`, `ebeam/hvsem/<feature>/` — features that exist for one tool only (e.g. `cdsem/device_statistics/`). Each sub-feature folder is its own Blueprint.

To add a new feature:

1. Decide whether it is shared (most common) or tool-specific. Most CD-SEM features will eventually need an HV-SEM equivalent — start in `hitachi/` unless the data shape genuinely diverges.
2. Create `back_dev_home/ebeam/<scope>/<feature>/` with `__init__.py`, `routes.py`, `data.py`.
3. In `routes.py`, declare `bp = Blueprint("<scope>_<feature>", __name__)` — the prefix keeps Blueprint names globally unique. For shared features, use `bp = Blueprint("hitachi_<feature>", __name__)`.
4. URL paths inside `routes.py`:
   - Shared: `@bp.get("/<tool_slug>/<feature>/...")`, validate `tool_slug` against `VALID_TOOL_SLUGS`.
   - Tool-specific: `@bp.get("/<tool>/<feature>/...")` with the tool name baked in.
5. The blueprint loader in `back_dev_home/__init__.py` discovers any `routes.py` under the package and registers it under `/api`. No manual registration is needed.
