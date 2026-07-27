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

Check backing services through `GET /api/health/services` and resolved feature providers through `GET /api/health/providers`. The latter returns `site`, effective `mode`, and one `{feature, provider, reason}` row per discovered feature. Local identity defaults to a development user; do not infer cloud authentication behavior from local mode.

## Configuration model

| Concern | Setting | Current default/behavior |
| --- | --- | --- |
| Backend dev port | `PORT` | `5050` in `index.py` |
| Frontend dev port | `NUXT_PORT` | `3000` |
| Nuxt proxy target | `NUXT_API_TARGET` | `http://localhost:5050` |
| Browser API base | `NUXT_PUBLIC_API_BASE` | `/api` |
| Runtime site | `SKEWNONO_SITE` | Explicit `home`/`office`; otherwise cloud path and hostname detection |
| Extra office hosts | `SKEWNONO_OFFICE_HOSTNAMES` | Comma-separated hostnames outside the tracked `PC...` convention |
| Provider mode | `SKEWNONO_DATA_PROVIDER` | `mock` is a whole-instance kill switch; `office` enables only adapters present on this machine |
| Feature source | `SKEWNONO_<FEATURE>_PROVIDER` | Highest precedence; explicit `office` fails if that adapter is absent |
| Session secret | `SKEWNONO_SECRET_KEY` | Development-only fallback; set in production |
| Admin users | `SKEWNONO_ADMIN_USERS` | Mode-specific source defaults |
| Chat gateway | `CHAT_BASE_URL` | Public OpenRouter default is usable in mock mode but blocked in office mode |
| Extra blocked chat hosts | `CHAT_BLOCKED_HOSTS` | Comma-separated additions to the built-in office blocklist |

Use the tracked `back_dev_home/.env.example` as the non-secret template and copy it to the ignored `back_dev_home/.env` for local values. Never inspect or document live `.env` values. Configuration exists under backend/frontend environment files, but setup documentation should refer only to variable names and trusted secret-management procedures.

## Incremental office migration

Deployment mode and data provider are separate. On a fresh office checkout—or after pulling template changes—initialize every runnable local adapter with the safe setup command:

```bash
.venv/bin/python -m scripts.setup_office_adapters --dry-run
.venv/bin/python -m scripts.setup_office_adapters
```

The setup tool creates missing runnable adapters and refreshes copies proven stale against Git history. It skips stub templates, because merely creating `office.py` would switch a working mock feature to an intentional `NotImplementedError`, and skips locally edited copies because their ignored changes may exist nowhere else. Stale copies are backed up as `office.py.bak` before replacement. Use `.venv/bin/python -m scripts.sync_office_adapters` for status-only inspection; add `--diff <name>`, select adapter names, or use `--all --dry-run` before a broader refresh. Statuses are `MISSING`, `SYNCED`, `STALE`, and `EDITED`; force-overwrite an edited copy only after reviewing and preserving its local changes.

Do not commit `office.py`; reviewable implementation and contract changes belong in `office_example.py`. Restart Flask after setup or synchronization because adapter discovery is cached per process. With no feature overrides, home and unknown hosts use mock mode; recognized office/cloud sites use office only for features whose direct `providers/office.py` exists. `SKEWNONO_SITE=office` is useful for VPN verification without changing adapter selection rules.

Use mock overrides as rollback controls:

```bash
# Disable one broken adapter.
SKEWNONO_STORAGE_PROVIDER=mock PORT=5050 .venv/bin/python index.py

# Disable all non-overridden office adapters.
SKEWNONO_DATA_PROVIDER=mock PORT=5050 .venv/bin/python index.py
```

Feature-specific `=office` remains useful for a home/VPN contract gate, but it is accepted only when that feature's `office.py` exists; otherwise both application startup and direct provider imports fail with a copy command rather than silently serving mock. `SKEWNONO_DATA_PROVIDER=office` selects office mode but does not force unwired features.

At every startup, `skewnono.providers` logs the detected site, effective mode, office-feature count, and each feature's provider/reason. When Git history proves an active `office.py` matches an older template, startup also emits a `STALE office.py` warning with the synchronization command; locally edited copies are intentionally not warned about. This check is best-effort and cannot normally prove staleness in a deployment bundle without `.git`. `GET /api/health/providers` exposes live provider resolution, not freshness. Use those outputs to learn what this machine serves; use `docs/office-migration/STATUS.md` separately to determine whether the real source passed contract and screen verification. Follow the readiness criteria in [integration points](../integrations/integration-points.md#provider-readiness).

## Live alarm office deployment

Live alarm has two independent local adapters. First copy `back_dev_home/ebeam/hitachi/live_alarm/writer/` to the external scheduler service, create its ignored `office.py`, configure fab alarm addresses and `LIVE_ALARM_REDIS_*`, and register `run_once` every 15 seconds on the dedicated fast executor with the lock and misfire settings in `live_alarm/MIGRATION.md`. The scheduler-side and Flask-side clients must use Redis DB 0.

Confirm `skewnono:live_alarm:*` keys and that each `meta.polled_at` advances before copying `providers/office_example.py` to Flask's ignored `providers/office.py`. Restart Flask, confirm `live_alarm` through `/api/health/providers`, then inspect the endpoint's `feed_status`: `stale` means the registered writer heartbeat stopped; `not_configured` means the fab is absent from the writer address map. The writer is portable by design and must not import `back_dev_home`; reader/writer member compatibility is pinned by `test_written_members_are_readable_by_the_reader`.

## Build, package, and cloud deployment

Build and package the client-only SPA from the office working tree:

```bash
npm --prefix front-dev-home run build
.venv/bin/python -m scripts.pack_deploy
# Equivalent: .venv/bin/python -m scripts.pack_deploy --build
```

The default bundle is `dist/skewnono-<timestamp>/`. Packaging deliberately reads the working tree rather than `git archive`, so ignored `providers/office.py`, `back_dev_home/.env`, and `minio_handler/minio_config.py` are retained. It also writes `preflight.py`, `DEPLOY.md`, and `MANIFEST.txt`; the manifest records source provenance, dirty state, adapter roster, and pack-time warnings. Use `--strict` only when every advisory should block packaging; the current feasibility deployment permits a runnable mock-backed bundle. See `docs/deployment.md` for the authoritative transfer procedure.

Copy the bundle's contents directly under `/project/workSpace`, restore restrictive permissions because transfer may discard them, then preflight both before and after dependency installation:

```bash
chmod 700 /project/workSpace
chmod 600 /project/workSpace/back_dev_home/.env
chmod 600 /project/workSpace/minio_handler/minio_config.py
cd /project/workSpace
python preflight.py
pip install -r back_dev_home/requirements.txt
python preflight.py
uwsgi --ini wsgi.ini
curl localhost:5000/api/health/providers
```

Path and directory depth are runtime configuration: `_runtime/env.py` recognizes cloud mode only below `/project/workSpace`, and SPA lookup assumes the packaged depth. An extra wrapper directory or another installation path can leave the process returning HTTP while silently disabling cloud SSO, SPA mounting, and office-mode site classification. The standard-library-only preflight catches these layout errors and reports whether `hcputil.auth.sso` or `hcputil.auto.sso` is available from the cloud image.

`wsgi.ini` exposes HTTP on `0.0.0.0:5000`, with four processes, two threads per process, 60-second harakiri, and worker recycle after 1,000 requests. The SPA uses relative `/api`, so the feasibility and production hostnames can use the same bundle. Current deployment URLs are HTTP-only; follow `docs/deployment.md` rather than enabling secure-cookie/HSTS settings that would break those sessions. The [architecture overview](../architecture/overview.md#deployment-modes) explains the underlying mode coupling.

## Pre-deployment checks

```bash
# Frontend
cd front-dev-home
npm run typecheck
npm test
npm run lint
npm run build

# Backend, from root
.venv/bin/ruff check .
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

### Application refuses to start for provider configuration

The app validates provider settings before registering routes. Invalid values fail immediately. A feature-specific `SKEWNONO_<FEATURE>_PROVIDER=office` also fails when its ignored `providers/office.py` is absent; use the copy command in the error or remove the override. Duplicate feature directory slugs and office adapters without mock siblings also fail registry validation.

### Office feature is unexpectedly mock or returns NotImplementedError

Query `GET /api/health/providers` or inspect the startup table first. In office mode, reason `no providers/office.py` means the machine-local adapter is absent; use the setup/sync workflow, restart, and rerun its contract gate. A selected adapter that raises `NotImplementedError` remains intentionally unwired; remove that stub copy or use a feature-specific mock override while diagnosing it. Hardware is the exception: its feature-level adapter dispatches each tab separately, and a missing nested tab `office.py` falls back to that tab's mock with an INFO log.

### Office feature returns JSON 502 or 503

`502 upstream_data_error` means a backing key, alias, or serialized DataFrame is missing or malformed. `503 backend_unavailable`/`backend_unreachable` means required configuration is absent or Redis/OpenSearch could not connect or timed out. Correct the upstream source or non-secret environment configuration rather than treating these responses as route failures.

### Office chat returns `403 egress_blocked`

The chat egress guard rejected `CHAT_BASE_URL` because its host matches a built-in public LLM gateway or an entry added through `CHAT_BLOCKED_HOSTS`. Configure an approved internal gateway; custom blocked hosts only tighten the policy and cannot remove defaults. The failed user turn remains stored so it can be retried without duplication after configuration is corrected.

### Measurement images fail or receive 429

All endpoints named `msr_image.*` are limiter-exempt. A `400 invalid_tool_ip` points to an invalid IPv4 address or `SKEWNONO_TOOL_SUBNETS` mismatch; unsafe class, MSR, and image-name path segments are also rejected before FTP access. `429 too_many_jobs` means the configured active-job cap was reached. The tracked office adapter selects the HTTP-proxy downloader on Windows and direct FTP elsewhere, but real office operation still requires an ignored `msr_image/providers/office.py`, a distinct MinIO cache prefix, and representative source verification. Gallery polling exposes whole-job listing errors separately from per-file failures; TIFF originals intentionally render as download links.

### Rate limits or local state behave inconsistently across workers

The limiter uses `memory://`, and several home providers are in-memory/SQLite oriented. Measurement-image jobs use Redis only when the selected provider is office and `REDIS_HOST` is configured; otherwise they use process memory. Multi-worker office deployment therefore needs Redis to prevent valid polls reaching another worker as `404 unknown_job`. Job TTL and maximum-active settings are enforced, although Redis admission is a soft cross-worker guard rather than a fully atomic global cap. The app starts one idempotent image-cache purge scheduler per process. Connect intended shared persistence for other local state or reduce the process model only for diagnosis.

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
