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

Automatic route discovery makes a feature self-registering, but every discovered module is imported at startup. A broken import or a `routes.py` without `bp` prevents the entire app from booting.

Shared CD-SEM/HV-SEM features belong under `back_dev_home/ebeam/hitachi/<feature>/`; genuinely tool-specific behavior belongs under `ebeam/cdsem/` or `ebeam/hvsem/`. `back_dev_home/README.md` documents this scope decision.

## Provider seam and contracts

A route should depend on functions exported by its sibling `data.py`, never on OpenSearch, MinIO, FTP, or Redis directly. `back_dev_home/_runtime/data_provider.py` resolves the provider in this order:

1. `SKEWNONO_<FEATURE>_PROVIDER`;
2. `SKEWNONO_DATA_PROVIDER`;
3. `office` when `_runtime/site.py` recognizes an office/cloud site and the feature is in `OFFICE_READY`;
4. otherwise `mock`.

Site detection itself prefers `SKEWNONO_SITE`, then treats the path-derived cloud deployment as office, then checks normalized hostnames (`PC...` or `SKEWNONO_OFFICE_HOSTNAMES`). Unknown hosts stay mock. This lets office-ready features move without a blanket switch that would activate unfinished adapters, while explicit provider variables remain authoritative.

The dispatcher calls `providers/mock.py` or a local `providers/office.py`. Home authors maintain tracked `providers/office_example.py`; office engineers copy it to the gitignored `office.py` and verify it against local sources. Routes and frontend composables retain the same shape, while runtime `TypedDict` validation in `_core/contract_check.py` allows extra office document fields but rejects missing required keys or wrong nested types.

This architecture [depends on integration adapters](../integrations/integration-points.md) without allowing transport details to leak into product routes. `_runtime/office_redis.py` now centralizes environment loading, one cached fail-fast Redis pool per process, and parquet-first DataFrame decoding; feature adapters still own normalization. Missing upstream data becomes JSON `502 upstream_data_error`, while bare configuration failures and Redis/OpenSearch connection or timeout failures become JSON `503` responses. Subclassed programming errors such as `KeyError` and `NotImplementedError` intentionally remain 500s.

## Identity, authorization, and observability

`_auth/middleware.py` accepts a `Bearer skn_...` API token first, then the selected user identity provider. Local mode reads development identity values; cloud mode lazily imports the internal SSO library. Admin membership is centralized in `_auth/admin.py` and can be configured with `SKEWNONO_ADMIN_USERS`.

Blocked users may still receive the SPA shell so the client can render a denial experience, but `/api/*` requests are rejected. The frontend gate in `app/app.vue` loads the current activity/user record before rendering protected content.

`_logging/activity.py` records request latency, feature mapping, exceptions, and human activity. API-token traffic is logged with zero human-activity weight, so automation does not inflate usage analytics. In cloud mode, structured logs can flow to OpenSearch as described in [integration points](../integrations/integration-points.md).

The default limit is `20 per 5 seconds`, keyed by user or remote address. MSR image delivery is exempt because one gallery opens many cacheable image requests. Limiter state is currently process-local (`memory://`), which matters under the four-process uWSGI configuration.

## Deployment modes

Deployment mode and data provider remain separate, but deployment site contributes a safe provider default:

- `_runtime/env.py:is_cloud()` decides cloud SSO, OpenSearch logging, SPA serving, and bind behavior based on installation path.
- `_runtime/site.py` classifies explicit, cloud, and recognized-host runs as home or office.
- provider environment variables override that classification; only `OFFICE_READY` features auto-select office.

An office-local process can therefore use office data without cloud SSO or SPA serving. Path-derived cloud detection is still brittle for deployment behavior, though treating cloud as an office site prevents a production VM hostname change from silently selecting mock data.

In cloud mode, `_spa/serving.py` serves files from `front-dev-home/.output/public` and falls back to `index.html` for client routes, while refusing to swallow `api/*`. Missing output logs a warning and leaves an API-only service rather than failing startup. Build and deployment procedures live in the [operations runbook](../operations/runbook.md).

## Change impact checklist

- **Add a page:** check route navigation, URL-state preservation, API calls, and access gate.
- **Add an API feature:** add a scoped folder with `routes.py`, `data.py`, providers, contracts, and contract tests; no central registration edit is needed.
- **Change a response:** update backend contracts, API-contract docs, composable types, consumers, fixtures, and [tests](../testing/guidance.md) together.
- **Connect office data:** implement the tracked `providers/office_example.py`, copy it to ignored `providers/office.py` for office verification, keep the route unchanged, and run that feature's active-provider contract gate. Add it to `OFFICE_READY` only after its rollout status justifies automatic office selection.
- **Change auth/logging:** inspect API tokens, blocked-member behavior, activity weighting, rate limits, and multi-worker consequences.
