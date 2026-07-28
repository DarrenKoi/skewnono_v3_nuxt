---
type: Architecture Guide
title: Runtime Architecture
description: Architecture of the SKEWNONO Nuxt SPA and Flask API, including request flow, dynamic Blueprint registration, data-provider switching, security middleware, and production SPA serving.
resource: back_dev_home/__init__.py
tags: [architecture, nuxt, flask, api, providers]
---

# Runtime architecture

## System shape

The [SKEWNONO product domains](../domain/concepts.md) share one Nuxt 4 client and one feature-sliced Flask application. `front-dev-home/nuxt.config.ts` sets `ssr: false`; in development Nitro proxies `/api`, while production Flask serves generated static files. This avoids a production Node runtime and supports the internal/offline network.

```text
Browser
  -> Nuxt route in front-dev-home/app/pages/
  -> view components and composables
  -> runtimeConfig.public.apiBase (default /api)
  -> Flask application
  -> cross-cutting middleware
  -> feature Blueprint
  -> data.py provider dispatcher
  -> providers/mock.py or the local providers/office.py
```

The concrete startup entry is `index.py`, which exposes both `app` and `application`. `wsgi.ini` imports `index:application` for uWSGI.

## Frontend boundaries

Pages are file-routed under `front-dev-home/app/pages/`; reusable UI lives under `app/components/`, and API/state behavior generally lives under `app/composables/`. Composables use `$fetch` and Nuxt `useAsyncData`, not TanStack Query. `useSemListApi.ts` is the reference shared-resource pattern: one cache key, a module-scoped in-flight promise, and derived `computed` subsets.

Frontend state uses Nuxt built-ins rather than Pinia. `app/stores/navigation.ts` wraps `useState`, while `app/composables/usePersistedState.ts` is the canonical factory for state that must also survive a reload. The factory returns one shared `useState` ref per state key, validates stored values, and writes through a detached `flush: 'sync'` watcher so acknowledged cart, preset, preference, recent-search, and selection changes are durable before a tab can close. Existing storage keys and formats remain stable across the refactor; new composables should call the factory instead of duplicating localStorage watchers. `useNavigation.ts` separately centralizes path changes and preserves URL query state where shareability matters, directly supporting the [key workflows](../workflows/key-workflows.md).

## Flask composition

`back_dev_home/__init__.py:create_app()`:

1. Loads backend environment configuration and creates Flask.
2. Installs JSON HTTP-error handling.
3. Selects local or cloud identity and installs access middleware.
4. Installs activity/request logging.
5. Seeds local demo activity users outside cloud mode.
6. Recursively imports every non-private `routes.py` and requires a Blueprint named `bp`.
7. Registers each feature Blueprint under `/api`.
8. In cloud mode, registers login and SPA serving.
9. Installs a per-user/IP API rate limiter.

Automatic route discovery makes a feature self-registering, but every discovered module is imported at startup. A broken import or a `routes.py` without `bp` prevents the entire app from booting. After route and limiter setup, `create_app()` also starts the [measurement-image cache](../integrations/integration-points.md#measurement-image-delivery-and-cache) purge scheduler. Under multi-process serving this creates one idempotent nightly sweep per worker, not one cluster-wide scheduler.

Shared CD-SEM/HV-SEM features belong under `back_dev_home/ebeam/hitachi/<feature>/`; genuinely tool-specific behavior belongs under `ebeam/cdsem/` or `ebeam/hvsem/`. `back_dev_home/README.md` documents this scope decision.

## Provider seam and contracts

A route should depend on functions exported by its sibling `data.py`, never on OpenSearch, MinIO, FTP, or Redis directly. Provider selection combines machine mode with adapter presence:

1. `SKEWNONO_<FEATURE>_PROVIDER` explicitly selects that feature; `office` is accepted only when its adapter exists.
2. Otherwise, `SKEWNONO_DATA_PROVIDER` selects the process mode, or mode follows `_runtime/site.py`.
3. Office mode selects `office` only for features with a local `providers/office.py`; all other features remain `mock`. Mock mode selects mock for every non-overridden feature.

Site detection prefers `SKEWNONO_SITE`, then treats the path-derived cloud deployment as office, then checks normalized hostnames (`PC...` or `SKEWNONO_OFFICE_HOSTNAMES`). Unknown hosts stay mock. `_runtime/office_registry.py` discovers features from direct `providers/mock.py` children and readiness from direct `providers/office.py` children; the scan is cached, so adding an adapter requires a restart. Duplicate feature slugs and office adapters without mock siblings fail validation. Hardware's nested tab adapters are deliberately excluded and use their own fallback.

The dispatcher calls `providers/mock.py` or the ignored, machine-local `providers/office.py`. Home authors maintain tracked `providers/office_example.py`; office engineers use the [adapter setup and synchronization workflow](../operations/runbook.md#incremental-office-migration) to create or refresh local copies, then verify them against local sources. `_runtime/office_template.py` classifies each copy as `MISSING`, `SYNCED`, `STALE`, or `EDITED` from current and recent Git templates. Boot warns only when a running copy is provably stale; locally edited copies are preserved without warning because their ignored changes may be intentional and unique. Freshness diagnosis is best-effort and never blocks startup.

`create_app()` rejects invalid provider values and any explicit feature `=office` that cannot be honored, then logs every feature's provider and reason through `skewnono.providers`. The same resolution is exposed by `GET /api/health/providers`, which reads runtime state directly rather than through the swappable health provider. Routes and frontend composables retain the same shape, while runtime `TypedDict` validation in `_core/contract_check.py` allows extra office document fields but rejects missing required keys or wrong nested types.

This architecture [depends on integration adapters](../integrations/integration-points.md) without allowing transport details to leak into product routes. `_runtime/office_redis.py` now centralizes environment loading, one cached fail-fast Redis pool per process, and parquet-first DataFrame decoding; feature adapters still own normalization. Missing upstream data generally becomes JSON `502 upstream_data_error`, while configuration and backing-service failures become JSON `503` responses. Activity and admin-log readers deliberately use endpoint-specific `activity_query_failed` and `log_query_failed` 503 contracts rather than falling back to mock or empty data; asynchronous log delivery instead drops on failure and exposes diagnostics through `/api/health/logging`. Subclassed programming errors such as `KeyError` and `NotImplementedError` intentionally remain 500s.

## Identity, authorization, and observability

`_auth/middleware.py` accepts a `Bearer skn_...` API token first, then the selected user identity provider. Identity selection follows `_runtime/env.py:is_cloud()` independently of mock/office data-provider mode: local identity reads `LASTUSER` or `LAST_USER` cookies and otherwise uses `local-dev`, while cloud identity lazily tries `hcputil.auth.sso` and then the documented `hcputil.auto.sso` compatibility spelling. Admin membership is centralized in `_auth/admin.py` and can be configured with `SKEWNONO_ADMIN_USERS`.

Blocked users may still receive the SPA shell so the client can render a denial experience, but `/api/*` requests are rejected. The frontend gate in `app/app.vue` loads the current activity/user record before rendering protected content.

`_logging/activity.py` records a canonical request document with request ID, latency, feature, normalized FAB context, sanitized query, identity, status, exception correlation, and human-activity classification. Anonymous, API-token, failed, administrative, health, and registered background requests carry zero activity weight; authenticated successful entry/feature requests drive analytics. Cloud requests that successfully serve a built SPA file are excluded, while `index.html` fallbacks remain logged so app entry, deep-link reloads, unknown routes, and missing-asset deployment symptoms stay observable. When OpenSearch credentials are configured and logging is not explicitly disabled, `_logging/target.py` requires `SKEWNONO_LOG_ENV=local|production` and the bounded asynchronous handler ships to the corresponding alias described in [integration points](../integrations/integration-points.md). Request bodies, headers, cookies, and authorization values are not captured.

The default limit is `20 per 5 seconds`, keyed by user or remote address. The entire `msr_image` Blueprint is exempt because one gallery can open many cacheable requests. Limiter state remains process-local (`memory://`). Image download jobs select Redis shared state only when the provider is office and `REDIS_HOST` is configured; other runs use memory. Job TTL and active-job limits are enforced in both implementations, although Redis admission can briefly exceed the cap under simultaneous cross-worker creation. Multi-worker office serving therefore depends on the [measurement-image integration](../integrations/integration-points.md#measurement-image-delivery-and-cache) being configured with Redis.

## Deployment modes

Deployment mode and data provider remain separate, but deployment site contributes a safe provider mode:

- `_runtime/env.py:is_cloud()` decides cloud SSO, SPA serving, and bind behavior based on installation path; OpenSearch logging target selection is independent and explicit.
- `_runtime/site.py` classifies explicit, cloud, and recognized-host runs as home or office.
- `SKEWNONO_DATA_PROVIDER` can override that mode; each feature still needs a local office adapter before office mode selects it.

An office-local process can therefore use office data without cloud SSO or SPA serving. Path-derived cloud detection is still brittle for deployment behavior, though treating cloud as office mode prevents a production VM hostname change from silently selecting mock for adapters that are present.

In cloud mode, `_spa/serving.py` serves files from `front-dev-home/.output/public` and falls back to `index.html` for client routes, while refusing to swallow `api/*`. Missing output logs a warning and leaves an API-only service rather than failing startup. The supported packager preserves the exact SPA output and ignored office runtime files, then supplies a standard-library preflight. Bundle contents must sit directly under `/project/workSpace`; both that path and the internal directory depth are load-bearing because they control cloud detection and SPA resolution. Build and deployment procedures live in the [operations runbook](../operations/runbook.md#build-package-and-cloud-deployment).

## Change impact checklist

- **Add a page:** check route navigation, URL-state preservation, API calls, and access gate.
- **Add an API feature:** add a scoped folder with `routes.py`, `data.py`, providers, contracts, and contract tests; no central registration edit is needed.
- **Change a response:** update backend contracts, API-contract docs, composable types, consumers, fixtures, and [tests](../testing/guidance.md) together.
- **Connect office data:** implement the tracked `providers/office_example.py`, copy it to ignored `providers/office.py`, restart so presence is rescanned, keep the route unchanged, run that feature's active-provider contract gate, and verify its row through the boot table or `/api/health/providers`. Update the migration ledger only after representative real-data and screen verification.
- **Change auth/logging:** inspect API tokens, blocked-member behavior, activity weighting, rate limits, and multi-worker consequences.
