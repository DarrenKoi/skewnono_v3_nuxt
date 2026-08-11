---
type: Operations Runbook
title: Development and Deployment Runbook
description: Practical commands and diagnostics for identity, configuration, office adapters, scheduled jobs, live alarms, image previews, overlay packaging, and SKEWNONO home, office, and cloud operation.
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
| Session secret | `SKEWNONO_SECRET_KEY` | Development-only fallback at home; cloud startup and preflight require a nonblank value |
| Trusted proxy address | `SKEWNONO_TRUST_PROXY` | Off by default; truthy enables exactly one trusted `X-Forwarded-For` hop |
| Admin users | `SKEWNONO_ADMIN_USERS` | Mode-specific source defaults |
| Logging target | `SKEWNONO_LOG_ENV` | Required as `local` or `production` when OpenSearch logging credentials are configured; selects the shared writer/reader alias |
| Logging kill switch | `OPENSEARCH_LOGGING_DISABLED` | `1`, `true`, or `yes` skips the asynchronous log shipper without changing reader/provider selection |
| Chat gateway | `CHAT_BASE_URL` | Public OpenRouter default is usable in mock mode but blocked in office mode |
| Chat runtime | `SKEWNONO_CHAT_RUNTIME` | `direct`; use `agent` only with a tool-capable model and prepared knowledge source |
| Chat page gate | `SKEWNONO_CHAT_UNDER_DEVELOPMENT` | Defaults on in cloud; `0` launches the page but does not authorize APIs |
| Extra blocked chat hosts | `CHAT_BLOCKED_HOSTS` | Comma-separated additions to the built-in office blocklist |
| Scheduler startup | `SKEWNONO_SCHEDULER_ENABLED` | Enabled; false-like values disable scheduled jobs |
| Image-cache retention | `IMAGE_CACHE_TTL_HOURS` | `72`; the external safety sweep must match |

Use the tracked `back_dev_home/.env.example` as the non-secret template and copy it to the ignored `back_dev_home/.env` for local values. Never inspect or document live `.env` values. Configuration exists under backend/frontend environment files, but setup documentation should refer only to variable names and trusted secret-management procedures.

## Identity checks

Every phase exposes `GET /api/me`. Identity precedence is API token, `LASTUSER`/legacy `LAST_USER` cookie, signed self-declaration, then `local-dev` at home or `anonymous` in cloud. Cloud users with no cookie are sent by Nuxt to `/identify`; accepted declarations last 30 days and may carry `verified: false` when the `members` directory has no row or is unavailable. They remain non-admin regardless of employee number. Use the header release action or `DELETE /api/identify` to clear a declaration.

Before cloud rollout, confirm the hosting layer forwards `LASTUSER`. If it does not, the application remains usable but all new browser sessions initially appear as `anonymous`, masking an infrastructure problem as a self-identification workflow. When nginx or another trusted proxy terminates connections, enable `SKEWNONO_TRUST_PROXY` only if exactly one proxy supplies `X-Forwarded-For`; leaving it off is safer for the current direct uWSGI socket because clients could otherwise forge addresses.

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

Live alarm has one machine-local swap surface and no external writer or scheduler. Implement `office_utils.live_alarm.get_ebeam_metrology_alarms(fac_id)` with an upstream timeout shorter than the 20-second Redis lock TTL, then copy `back_dev_home/ebeam/live_alarm/providers/office_example.py` to the ignored `providers/office.py`. The source must return the unfiltered facility alarm rows; application normalization selects Hitachi ALIDs `9006`, `9007`, and `9035`.

Restart Flask and confirm `live_alarm` through `/api/health/providers`. Open a representative single- and multi-FAB board, then inspect `skewnono:live_alarm:*` and the response fields: `live` means every configured facility was fetched successfully within 90 seconds; `stale` means at least one facility has no recent successful fetch, so check for `live_alarm refresh failed`; `not_configured` means none of the selected FABs has that tool type in SEM-list. Nonzero `unmatched_count` identifies alarm equipment absent from the roster, while `not_configured_fabs` reports only the missing subset when other selected FABs can still render. Demand refresh is capped at one upstream call per distinct facility per 20 seconds, regardless of viewer count; selected sibling FABs that share a facility reuse the same call and Redis board. Follow `back_dev_home/ebeam/live_alarm/MIGRATION.md` for the source schema and verification procedure.

## Recipe IDP office probe

From the repository root, run the diagnostic without filters to inspect the newest measurement document and maximize the chance of reaching a real recipe file:

```bash
.venv/bin/python -m scripts.probe_recipe_ftp
# Narrow deliberately when required:
.venv/bin/python -m scripts.probe_recipe_ftp --tool hvsem --eqp MHV101 --date 2026-07-26
```

The probe queries measurement history, validates the tool IP, derives and lists the FTP path, downloads the `.idp`, parses `wafer_mp_info`, `wafer_align_info`, and `idp_image_info`, prints their columns and dtypes, and lists the raw-recipe directory. A parser failure preserves the downloaded file and traceback but returns a nonzero status. In a Python console, call `probe = main([])` or pass an explicit argument list; the returned `Probe` retains successful-stage evidence for inspection (`scripts/probe_recipe_ftp.py`). This procedure exercises the [recipe FTP integration](../integrations/integration-points.md#ftp-ingestion) without replacing its contract tests.

## Build, package, and cloud deployment

Build and package the client-only SPA from the office working tree:

```bash
npm --prefix front-dev-home run build
.venv/bin/python scripts/deploy/pack.py
```

The default artifact is an **overlay bundle** under `dist/`: it deliberately excludes the permanent cloud-root `index.py` and `wsgi.ini`, which must already exist under `/project/workSpace`. Packaging reads the working tree rather than `git archive`, so ignored `providers/office.py`, `back_dev_home/.env`, and `minio_handler/minio_config.py` are retained. It also writes `preflight.py`, `DEPLOY.md`, and `MANIFEST.txt`; the manifest records source provenance, dirty state, adapter roster, and pack-time warnings. Use `--strict` only when every advisory should block packaging; the current feasibility deployment permits a runnable mock-backed overlay. See `docs/deployment.md` for the authoritative transfer procedure.

Overlay the bundle's contents directly onto the existing `/project/workSpace` without deleting its permanent root boot files. Restore restrictive permissions because transfer may discard them, then preflight both before and after dependency installation:

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

Path and directory depth are runtime configuration: `_runtime/env.py` recognizes cloud mode only below `/project/workSpace`, and SPA lookup assumes the packaged depth. An extra wrapper directory or another installation path can leave the process returning HTTP while silently selecting the local fallback identity, disabling SPA mounting, and selecting the wrong provider mode. The standard-library-only preflight catches these layout errors, requires the permanent `index.py` and `wsgi.ini`, reports that identity comes from the `LASTUSER` cookie, and verifies that `back_dev_home/.env` chooses a nonblank `SKEWNONO_SECRET_KEY` before uWSGI can enter a boot loop.

`wsgi.ini` exposes HTTP on `0.0.0.0:5000`, with four processes, four threads per process, 120-second harakiri, and worker recycle after 1,000 requests. The SPA uses relative `/api`, so the feasibility and production hostnames can use the same bundle. Current deployment URLs are HTTP-only; follow `docs/deployment.md` rather than enabling secure-cookie/HSTS settings that would break those sessions. The [architecture overview](../architecture/overview.md#deployment-modes) explains the underlying mode coupling.

## Pre-deployment checks

```bash
# Frontend
cd front-dev-home
npm run typecheck
npm test
npm run lint       # manual; not an active root CI gate
npm run build      # manual; not an active root CI gate

# Backend, from root
.venv/bin/ruff check .
.venv/bin/python -m pytest tests back_dev_home -q

# Documentation (manual)
npm run lint:md
```

For a provider migration, rerun the feature contract gate with its office override. For measurement-image changes, also run the focused single-flight, route, and warmer-policy suites listed in [testing guidance](../testing/guidance.md#feature-contract-gates). See [testing guidance](../testing/guidance.md).

## Measurement-image load verification

The image feature has two distinct load controls: warm jobs are bounded by the Redis-backed `max_jobs`/FTP-concurrency policy, while cold GETs deduplicate concurrent requests only within each process through the per-cache-key single-flight gate. Do not add a second warm job while polling an existing one, and do not treat an ordinary polling failure as proof that the job is gone; the warmer retries transient failures within its remaining ceiling and only releases the panel for a definitive `404`/`unknown_job` or exhausted budget. A refused POST is retryable only when it is `429` with `too_many_jobs`.

Before office activation or after FTP/proxy changes, run the measurement probe against representative equipment and compare login, transfer, concurrency, proxy-cap, and cache-write timings rather than changing timeout/concurrency constants from guesses:

```bash
.venv/bin/python -m scripts.measure_msr_image_ftp
```

Verify the tracked adapter is copied to the ignored `back_dev_home/msr_image/providers/office.py`, restart Flask so provider discovery is refreshed, and confirm `/api/health/providers` plus representative gallery original/preview responses. Use `SKEWNONO_MSR_IMAGE_PROVIDER=mock` as the narrow rollback if the office adapter is unhealthy; use the broader `SKEWNONO_DATA_PROVIDER=mock` only when all non-overridden office adapters must be disabled. The external cache sweep must retain the same `IMAGE_CACHE_TTL_HOURS` (72 by default).

## OpenSearch logging rollout and diagnosis

Logging writes and activity/admin-log reads share the target resolved from `SKEWNONO_LOG_ENV`; provider selection alone does not choose an alias. Before office activation, copy the tracked activity and admin-log adapters, review the read-only provisioning plan, then apply it only from an authorized company-network environment:

```bash
.venv/bin/python ops_index_mgmt/skewnono_logging.py --dry-run
# Mutates templates, policies, backing indices, and aliases after review:
.venv/bin/python ops_index_mgmt/skewnono_logging.py
```

A no-argument run provisions both local and production families; use `--environment local|production|all` only to target the run deliberately. The script best-effort loads the ignored backend environment when `OPENSEARCH_HOST` is not already exported.

The expected write aliases are `skewnono_logging_local-000001 -> skewnono_logging_local` and `skewnono_logging-000001 -> skewnono_logging`. Validate an existing rollover target with `exists_alias()` plus the alias entry's numbered `write_index`; a generic `HEAD /<target>` also resolves aliases, so `OSIndex.describe()` may misreport a healthy alias as an index. Restart Flask and inspect `GET /api/health/logging`: `installed: false` means the shipper was disabled or credentials were absent; an installed response exposes target, queue depth, retry/failure/drop totals, and last success/failure timestamps. Delivery failures never fail the originating request, so rising drops or a stale success timestamp are the operational alarm. By contrast, `/activity` and `/admin/logs` surface OpenSearch/configuration failures as `503 activity_query_failed` and `503 log_query_failed`; do not treat those as valid empty datasets. This rollout [activates the shared OpenSearch integration](../integrations/integration-points.md#opensearch), and real-data verification remains required before the migration ledger moves from implemented to office.

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

The app validates provider settings before registering routes. Invalid values fail immediately. A feature-specific `SKEWNONO_<FEATURE>_PROVIDER=office` also fails when its ignored `providers/office.py` is absent; use the copy command in the error or remove the override. The boot validator also rejects `storage=office` when `sem_list` resolves to mock; copy the SEM-list office adapter too, or force storage back to mock. Duplicate feature directory slugs and office adapters without mock siblings also fail registry validation.

### Office feature is unexpectedly mock or returns NotImplementedError

Query `GET /api/health/providers` or inspect the startup table first. In office mode, reason `no providers/office.py` means the machine-local adapter is absent; use the setup/sync workflow, restart, and rerun its contract gate. A selected adapter that raises `NotImplementedError` remains intentionally unwired; remove that stub copy or use a feature-specific mock override while diagnosing it. Hardware is the exception: its feature-level adapter dispatches each tab separately, and a missing nested tab `office.py` falls back to that tab's mock with an INFO log.

### Storage refuses to boot with an office adapter

If startup reports that `storage=office` cannot use `sem_list=mock`, copy or implement `back_dev_home/sem_list/providers/office.py` and restart, or set `SKEWNONO_STORAGE_PROVIDER=mock` as a rollback. The validator prevents a silent empty storage join caused by different roster universes.

### Office feature returns JSON 502 or 503

`502 upstream_data_error` means a backing key, alias, or serialized DataFrame is missing or malformed. `503 backend_unavailable`/`backend_unreachable` means required configuration is absent or Redis/OpenSearch could not connect or timed out. Correct the upstream source or non-secret environment configuration rather than treating these responses as route failures.

### Office chat returns `403 egress_blocked`

The chat egress guard rejected `CHAT_BASE_URL` because its host matches a built-in public LLM gateway or an entry added through `CHAT_BLOCKED_HOSTS`. Configure an approved internal gateway; custom blocked hosts only tighten the policy and cannot remove defaults. The failed user turn remains stored so it can be retried without duplication after configuration is corrected.

### Measurement images fail or receive 429

All endpoints named `msr_image.*` are limiter-exempt. A `400 invalid_tool_ip` points to an invalid IPv4 address or `SKEWNONO_TOOL_SUBNETS` mismatch; unsafe class, MSR, and image-name path segments are also rejected before FTP access. `429 too_many_jobs` means the configured active-job cap was reached. The tracked office adapter selects the HTTP-proxy downloader on Windows and direct FTP elsewhere, but real office operation still requires an ignored `msr_image/providers/office.py`, a distinct MinIO cache prefix, and representative source verification. Display URLs add `preview=1` for inline TIFF-to-WebP rendering while original-download URLs omit it; conversion failure falls back to original bytes. Original bytes and previews use separate cache keys, and only successful actual WebP conversions are cached as previews. Keep the external Airflow cache sweep equal to `IMAGE_CACHE_TTL_HOURS` (72 hours by default); changing only the app window defeats its app-downtime safety role. Run `scripts/measure_msr_image_ftp.py` before changing `_SECONDS_PER_IMAGE` or proxy-timeout assumptions; its login, transfer, fan-out, and optional MinIO PUT measurements are still `OFFICE-VERIFY`, not certified defaults.

### Rate limits or local state behave inconsistently across workers

The application-wide limiter uses shared Redis in office mode when `REDIS_HOST` is configured, with bounded connection timeouts and a per-process memory fallback; home or unconfigured runs use `memory://`. A fallback event restores availability but makes rate budgets worker-local again, so diagnose Redis before trusting enforcement totals. Measurement-image jobs independently use Redis only when the selected provider is office and `REDIS_HOST` is configured; otherwise they use process memory. Multi-worker office deployment therefore needs Redis to prevent valid polls reaching another worker as `404 unknown_job`. Job TTL and maximum-active settings are enforced, although Redis admission is a soft cross-worker guard rather than a fully atomic global cap. Scheduled maintenance is registered only by the elected shared scheduler process; office task locks protect against overlap during worker recycling.

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
