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

Health check: `GET http://localhost:5050/api/health/services`

Phase 1 serves on **5050**, not 5000 — macOS AirPlay Receiver holds 5000. `PORT`
overrides it. (Phase 2, the company localhost server, is the one on 5000.)

## Frontend integration

Run Nuxt with the proxy target pointing here:

```bash
cd ../front-dev-home
NUXT_API_TARGET=http://localhost:5050 npm run dev
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
    |   |-- _tool_specs.py       # slug <-> tool_type <-> vendor <-> adapter-folder registry (see below)
    |   |-- __fixtures__/        # tool_type_cases.json — shared by the Python and TS classifiers
    |   |-- storage/             # feature: per-tool storage inventory (all four tool slugs)
    |   |   |-- __init__.py      # re-exports `bp`
    |   |   |-- routes.py        # Blueprint("storage") — /api/<tool_slug>/storage*
    |   |   |-- contracts.py     # response shape, provider-independent
    |   |   |-- data.py          # provider dispatch (see get_data_provider())
    |   |   `-- providers/       # mock.py (Phase 1) + office_example.py (Phase 2/3 template)
    |   |-- device_statistics/   # feature: recipe + device stats (CD-SEM only, path hardcoded)
    |   |   |-- __init__.py      # re-exports `bp`
    |   |   |-- routes.py        # Blueprint("device_statistics") — /api/cdsem/device-statistics/*
    |   |   |-- contracts.py
    |   |   |-- data.py
    |   |   `-- providers/
    |   |-- hardware/            # feature: per-tab providers (bm_pm, bsm, fdc, mdc, reso_center, sce, sharpness)
    |   |   |-- routes.py        # Blueprint("ebeam_hardware") — /api/<tool_slug>/hardware/<eqp_id>/<service>
    |   |   `-- providers/<tab>/ # each tab is its own mock.py + office_example.py pair
    |   `-- <other features>/    # fail_issue, lateral_recipe, live_alarm, pm_planning,
    |                            # recipe_search, recipe_tat, skew — same
    |                            # routes.py/contracts.py/data.py/providers/ shape
    |-- sem_list/                # feature: cross-tool SEM list
    |   |-- __init__.py          # re-exports `bp`
    |   |-- routes.py            # GET /api/sem-list
    |   `-- data.py              # Phase 1 mock; swap surface for Phase 2/3
    |-- requirements.txt
    `-- README.md
```

Every `ebeam/<feature>/` folder sits directly under `ebeam/` — there is no
vendor or tool folder above it (`ebeam/hitachi/...`, `ebeam/cdsem/...` no
longer exist; the layout was flattened so a feature slug is the single,
globally-unique name the office-adapter registry keys on — see
[`docs/back-end/vendor-onboarding.md`](../docs/back-end/vendor-onboarding.md)
§2 for why a vendor-above-feature folder would make the app fail to boot).
Whether a feature covers one tool slug or all four is a routing choice inside
`routes.py` (`<tool_slug>` URL converter vs. a hardcoded path segment), not a
folder-location choice — see "Adding a new e-beam tool feature" below.

## Office migration (Phase 2)

Provider-backed features keep `routes.py`, `data.py`, and `contracts.py`
unchanged — the real source is implemented in the feature's
`providers/office.py`, normalized to `contracts.py`, and selected at runtime.
The rules for **which** provider answers a request (mode vs. per-feature
readiness, `SKEWNONO_DATA_PROVIDER` vs. `SKEWNONO_<FEATURE>_PROVIDER`) are in
[`docs/back-end/provider-selection.md`](../docs/back-end/provider-selection.md);
the interface contract each `providers/office.py` must satisfy is in
[`docs/back-end/office-data-adapters.md`](../docs/back-end/office-data-adapters.md).
This README does not restate either — as a concrete example, `storage` is
selected with `SKEWNONO_STORAGE_PROVIDER=office` and covers both
`/api/<tool_slug>/storage` and `/api/<tool_slug>/ppid-unavailable`.

## Adding a new e-beam tool feature

Every `ebeam/<feature>/` folder sits flat under `ebeam/` — there is no vendor
or per-tool folder above it. What varies per feature is **routing**, not
**location**:

- Features that apply to every tool slug (`cdsem`, `hvsem`, `veritysem`,
  `provision`) use Flask's `<tool_slug>` URL converter and validate against
  `VALID_TOOL_SLUGS` from `ebeam/_tool_specs.py` — e.g. `storage`'s
  `@bp.get("/<tool_slug>/storage")`.
- Features scoped to CD/HV-SEM only (not AMAT) check membership in
  `SEM_TOOL_TYPES` from the same module.
- Features that exist for exactly one tool hardcode that tool's path segment
  instead of taking a `<tool_slug>` — e.g. `device_statistics`'s
  `@bp.get("/cdsem/device-statistics/...")`.

`ebeam/_tool_specs.py` is the single source of truth for slug ↔ tool_type ↔
vendor ↔ adapter-folder (`SLUG_TO_TOOL_TYPE`, `TOOL_TYPE_TO_VENDOR`,
`SLUG_TO_ADAPTER`) and for the CD/HV-only scope (`SEM_TOOL_TYPES`). Read its
module docstring before classifying a tool by anything other than
`model_to_tool_type()` — `eqp_models`/`eqp_prefixes` are mock fodder, not
classifiers.

To add a new feature:

1. Decide the routing scope per the bullets above (all four tool slugs, CD/HV
   only, or one tool hardcoded).
2. Create `back_dev_home/ebeam/<feature>/` with `__init__.py` (re-exporting
   `bp`), `routes.py`, `data.py`, `contracts.py`, and `providers/{mock,office_example}.py`
   — see [`docs/back-end/vendor-onboarding.md`](../docs/back-end/vendor-onboarding.md)
   for the full onboarding procedure and why a feature name must be globally
   unique (the office-adapter registry fails to boot on a duplicate).
3. In `routes.py`, declare `bp = Blueprint("<feature>", __name__)`. Flask
   only requires Blueprint names to be unique across the whole app; run
   `grep -rn "Blueprint(" back_dev_home/` first to confirm no collision.
   Existing blueprints are not yet consistent — some still carry an
   `ebeam_` prefix left over from before the folder layout was flattened
   (`ebeam_hardware`, `ebeam_fail_issue`, …); new features should use the
   bare feature name.
4. URL paths inside `routes.py`:
   - All-slug: `@bp.get("/<tool_slug>/<feature>/...")`, validate `tool_slug`
     against `VALID_TOOL_SLUGS`.
   - Single-tool: `@bp.get("/<tool>/<feature>/...")` with the tool name baked
     in.
5. The blueprint loader in `back_dev_home/__init__.py` discovers any
   `routes.py` under the package (skipping `_`-prefixed folders) and
   registers it under `/api`. No manual registration is needed.
