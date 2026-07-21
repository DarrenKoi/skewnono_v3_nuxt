---
type: Operations Runbook
title: Development and Deployment Runbook
description: Practical commands and diagnostics for running, configuring, building, and deploying the SKEWNONO Nuxt frontend and Flask backend across mock, office-local, and cloud modes.
resource: index.py
tags: [operations, runbook, deployment, configuration, troubleshooting]
---

# Development and deployment runbook

## Local home-mode startup

From the repository root:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r back_dev_home/requirements-dev.txt
PORT=5050 .venv/bin/python index.py
```

From `front-dev-home/` in a second shell:

```bash
npm ci
NUXT_API_TARGET=http://localhost:5050 npm run dev
```

Current defaults are Flask `5050` and Nuxt `3000`. Use the Nitro `/api` proxy; do not build frontend URLs from backend hosts. On Windows, activate `.venv\Scripts\activate` and prefer `npm.cmd` if PowerShell blocks `npm.ps1`.

Check the backend through `GET /api/health/services`. Local identity defaults to a development user; do not infer cloud authentication behavior from local mode.

## Configuration model

| Concern | Setting | Current default/behavior |
| --- | --- | --- |
| Backend dev port | `PORT` | `5050` in `index.py` |
| Frontend dev port | `NUXT_PORT` | `3000` |
| Nuxt proxy target | `NUXT_API_TARGET` | `http://localhost:5050` |
| Browser API base | `NUXT_PUBLIC_API_BASE` | `/api` |
| Runtime site | `SKEWNONO_SITE` | Explicit `home`/`office`; otherwise cloud path and hostname detection |
| Extra office hosts | `SKEWNONO_OFFICE_HOSTNAMES` | Comma-separated hostnames outside the tracked `PC...` convention |
| Global data source | `SKEWNONO_DATA_PROVIDER` | Overrides site-based defaults when set |
| Feature source | `SKEWNONO_<FEATURE>_PROVIDER` | Highest-precedence provider override |
| Session secret | `SKEWNONO_SECRET_KEY` | Development-only fallback; set in production |
| Admin users | `SKEWNONO_ADMIN_USERS` | Mode-specific source defaults |
| Chat gateway | `CHAT_BASE_URL` | Public OpenRouter default is usable in mock mode but blocked in office mode |
| Extra blocked chat hosts | `CHAT_BLOCKED_HOSTS` | Comma-separated additions to the built-in office blocklist |

Use the tracked `back_dev_home/.env.example` as the non-secret template and copy it to the ignored `back_dev_home/.env` for local values. Never inspect or document live `.env` values. Configuration exists under backend/frontend environment files, but setup documentation should refer only to variable names and trusted secret-management procedures.

## Incremental office migration

Deployment mode and data provider are separate. On a fresh office checkout, create each local adapter from its tracked implementation:

```bash
cp back_dev_home/meas_hist/providers/office_example.py \
  back_dev_home/meas_hist/providers/office.py
```

Do not commit `office.py`; reviewable implementation and contract changes belong in `office_example.py`. With no explicit provider variables, home and unknown hosts use mock, while recognized office/cloud sites use office only for `_runtime/site.py:OFFICE_READY`; unfinished features stay mock. `SKEWNONO_SITE=office` is useful for VPN verification, and feature/global provider variables override the site default:

```bash
SKEWNONO_SITE=office \
SKEWNONO_MEAS_HIST_PROVIDER=office \
SKEWNONO_STORAGE_PROVIDER=mock \
PORT=5050 .venv/bin/python index.py
```

Keep `docs/office-migration/STATUS.md` aligned with `OFFICE_READY`. At present health and Recipe TAT are allowlisted but still labeled implemented-only in the ledger, so verify or temporarily override them before relying on unattended office/cloud defaults. A `NotImplementedError` usually means a selected adapter remains intentionally unwired. Follow the readiness criteria in [integration points](../integrations/integration-points.md#provider-readiness).

## Build and production-style serving

Build the client-only SPA:

```bash
cd front-dev-home
npm ci
npm run generate
```

The output must exist at `front-dev-home/.output/public`. In cloud mode, Flask serves real assets and falls back to `index.html` for Nuxt client routes. It does not route `api/*` to the SPA.

Serve Flask through:

```bash
uwsgi --ini wsgi.ini
# or an equivalent
gunicorn index:application
```

`wsgi.ini` currently exposes HTTP on `0.0.0.0:5000`, with four processes, two threads per process, 60-second harakiri, and worker recycle after 1,000 requests. Missing SPA output only produces a warning and leaves an API-only server; deployment automation should verify the directory explicitly.

The [architecture overview](../architecture/overview.md#deployment-modes) explains that cloud mode is inferred from installation path. Confirm the expected path before assuming SSO, SPA serving, or cloud logging is enabled.

## Pre-deployment checks

```bash
# Frontend
cd front-dev-home
npm run typecheck
npm test
npm run lint
npm run build

# Backend, from root
.venv/bin/python -m pytest tests back_dev_home -q

# Documentation
npm run lint:md
```

For a provider migration, rerun the feature contract gate with its office override. See [testing guidance](../testing/guidance.md).

## Troubleshooting

### Frontend gets 404 or calls the wrong server

- Confirm `NUXT_API_TARGET` matches Flask and includes no accidental `/api` suffix; Nuxt config appends it.
- Confirm frontend calls use `/api/...` or `runtimeConfig.public.apiBase`.
- Current home Flask default is 5050, despite older docs that say 5000.

### Direct browser requests fail CORS

The current Flask allowlist names `http://localhost:3100`, while Nuxt defaults to 3000. The normal Nitro proxy is same-origin and avoids CORS. If direct calls are required, align the allowlist deliberately rather than weakening it globally.

### Application fails during startup

Dynamic Blueprint discovery imports every non-private `routes.py`. Inspect the traceback for a feature import failure, missing optional dependency imported too early, or a module that does not export Blueprint `bp`.

### Office feature returns 500/NotImplementedError

Confirm the matching ignored `providers/office.py` exists and inspect its tracked `office_example.py` plus feature `MIGRATION.md`. Check `SKEWNONO_SITE`, global/feature provider variables, and whether the feature is in `OFFICE_READY`; an explicit global `office` can still select unfinished adapters. Use a feature-specific mock override while migrating other features.

### Office feature returns JSON 502 or 503

`502 upstream_data_error` means a backing key, alias, or serialized DataFrame is missing or malformed. `503 backend_unavailable`/`backend_unreachable` means required configuration is absent or Redis/OpenSearch could not connect or timed out. Correct the upstream source or non-secret environment configuration rather than treating these responses as route failures.

### Office chat returns `403 egress_blocked`

The chat egress guard rejected `CHAT_BASE_URL` because its host matches a built-in public LLM gateway or an entry added through `CHAT_BLOCKED_HOSTS`. Configure an approved internal gateway; custom blocked hosts only tighten the policy and cannot remove defaults. The failed user turn remains stored so it can be retried without duplication after configuration is corrected.

### Gallery images receive 429

`msr_file.msr_image` should be limiter-exempt. Confirm the Blueprint endpoint name has not changed. Other data requests are limited to 20 per 5 seconds per user/IP and can still expose runaway client loops.

### Rate limits or local state behave inconsistently across workers

The limiter uses `memory://`, and several home providers are in-memory/SQLite oriented. uWSGI runs multiple lazy app processes, so process-local state is not a shared production store. Connect the intended office persistence or reduce the process model only for diagnosis.

### Icons disappear in the office network

Runtime Iconify fallback is disabled. Add literal or dynamically named icons to the build-time client bundle configuration in `nuxt.config.ts`; do not rely on public network access.

### SPA URL returns API-only behavior

Confirm cloud mode is active and `front-dev-home/.output/public/index.html` exists. The server intentionally starts without SPA routes if output is absent.

## Operational cautions

- Set a strong production `SKEWNONO_SECRET_KEY`.
- Review any internal identifiers embedded in operational scripts before sharing logs or documentation.
- Keep API tokens out of URLs and chat; use Bearer headers and the human-session token management UI.
- Treat logs, MSR images, recipe data, and chat content as internal data.
- Do not run index-management scripts casually; `ops_index_mgmt/` changes aliases, templates, and lifecycle policy and is separate from application startup.
