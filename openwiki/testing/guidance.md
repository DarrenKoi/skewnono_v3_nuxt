---
type: Testing Guide
title: Testing and Quality Guidance
description: Test layers, Ruff checks, contract gates, fixture and CI coverage, and change-specific verification for SKEWNONO analytics, scheduler, chat RAG, live alarms, images, Flask, and Nuxt.
resource: tests
tags: [testing, pytest, node-test, contracts, ci]
---

# Testing and quality guidance

## Test layers

The repository combines backend route/integration tests, feature-local provider contracts, frontend pure-TypeScript tests, and a Python static gate. There is no single root command that runs every meaningful gate.

### Backend route and integration tests

Root tests under `tests/` use Flask clients and cover provider precedence, route filtering, response behavior, and office delegation. Runtime tests under `back_dev_home/_runtime/tests/` cover site detection, filesystem adapter discovery, resolution precedence, boot validation, provider-table logging, and Git-backed `STALE` versus `EDITED` template classification; `back_dev_home/health/tests/test_providers_route.py` covers live introspection. High-value suites include:

- `back_dev_home/_runtime/tests/test_site_provider.py`
- `back_dev_home/_runtime/tests/test_office_registry.py`
- `back_dev_home/_runtime/tests/test_boot_providers.py`
- `back_dev_home/_runtime/tests/test_office_template.py`
- `back_dev_home/health/tests/test_providers_route.py`
- `tests/test_pack_deploy.py` and `tests/test_preflight_cloud.py`
- `test_access_control.py`
- `test_activity_home.py`
- `test_afm_home.py`
- `test_meas_hist_search_home.py` and `test_meas_hist_search_local.py`
- `test_msr_file.py` and `test_lateral_recipe_local.py`
- `test_office_provider_dispatch.py`
- `test_recipe_analytics_home.py`
- `test_sem_list_home.py`
- `test_storage_home.py`

Run from the repository root:

```bash
.venv/bin/python -m pytest tests -q
```

### Feature contract gates

Provider-backed features colocate tests under `back_dev_home/**/tests/`. `_core/contract_check.py` validates required `TypedDict` fields and nested types while allowing extra source fields. This lets office documents carry unused fields without weakening required API behavior.

Run all backend tests:

```bash
.venv/bin/python -m pytest tests back_dev_home -q
```

Run a feature against the selected provider:

```bash
SKEWNONO_MEAS_HIST_PROVIDER=office \
  .venv/bin/python -m pytest back_dev_home/meas_hist -q
```

`back_dev_home/conftest.py` loads `back_dev_home/.env` for feature tests that import providers without creating the Flask app. This makes office-mode gates see the same connection variables as application startup; keep real values only in the ignored `.env`, never in tests or documentation.

For Redis-backed SEM list and storage, run standalone smoke checks and their contract gates from the repository root after copying tracked examples to `providers/office.py`:

```bash
.venv/bin/python -m back_dev_home.sem_list.providers.office
SKEWNONO_SEM_LIST_PROVIDER=office \
  .venv/bin/python -m pytest back_dev_home/sem_list -q

.venv/bin/python -m back_dev_home.ebeam.storage.providers.office
SKEWNONO_STORAGE_PROVIDER=office \
  .venv/bin/python -m pytest back_dev_home/ebeam/storage -q
```

The smoke commands load `back_dev_home/.env` through shared Redis plumbing and use the package `-m` form required by imports. The contract gates allow an empty office fleet while deterministic mock gates require data; office verification must still use representative sources and the corresponding [workflow](../workflows/key-workflows.md).

Provider-resolution changes must run `.venv/bin/python -m pytest back_dev_home/_runtime/tests back_dev_home/health/tests/test_providers_route.py -q`. The invariants are: unknown/home hosts remain mock; office mode flips only features with a direct `providers/office.py`; global `mock` disables all non-overridden office adapters; feature overrides win; explicit feature `office` without an adapter fails consistently at boot and direct import; hyphenated slugs normalize consistently; `storage=office` cannot pair with `sem_list=mock`; and the boot table plus health route report each feature's provider and reason. Tool-family changes also require `back_dev_home/ebeam/tests/test_tool_specs.py`, `back_dev_home/ebeam/tests/test_tool_type_parity.py`, `front-dev-home/app/utils/toolType.test.ts`, and `front-dev-home/app/utils/toolTypeParity.test.ts`. Registry tests also pin duplicate-slug/orphan rejection and exclude hardware's nested per-tab adapters. For Recipe TAT, test both the default ranked limit and `limit=0` (all buckets), plus lot-code bridge and empty-result behavior.

High-signal feature suites are `back_dev_home/_auth/tests/` plus `tests/test_rate_limit.py`, `test_app_factory_session.py`, and `test_app_error_handlers.py` for identity precedence, declarations, trusted admin sources, cloud session/proxy controls, shared limiter semantics, and JSON outage handling; `back_dev_home/msr_image/tests/` for route/cache/job/Redis/FTP-template behavior; `back_dev_home/ebeam/live_alarm/tests/` for normalization, demand refresh, locking, board merge, roster attribution, routes, and provider contracts; hardware's BM/PM, BSM, MDC, Reso Center, and SCE tests; `meas_hist/tests/test_ratio_normalization.py` plus `test_office_template.py` for complete fallback snapshots; recipe search's raw-path/route/normalization/align/IDP-locator suites; and lateral recipe's mock/office consistency tests. Logging changes must run `_logging/tests/`, activity/admin-log office-template and contract suites, `health/tests/test_logging_route.py`, and `tests/test_vendored_ops_index_mgmt.py`; these pin identity-source persistence, mode-gated installation, response-safe usage writes, classification/redaction, idempotent bounded delivery, KST aggregation, query/error contracts, diagnostics, and alias-policy agreement. Run the live-alarm suite after changing its source schema, ALID mapping, cache/lock policy, board window, roster attribution, or multi-FAB merge; run `back_dev_home/msr_image/tests/test_single_flight.py` and `test_routes_serve.py` for per-image leader/waiter result and error sharing, cache re-read, and unchanged 404/503 mapping; run `front-dev-home/app/utils/imageWarm.test.ts` plus the image app-wiring and `_scheduler` tests for refusal/poll retry classification, jitter ladder, remaining request budgets, actual ceiling enforcement, and scheduled cache cleanup. Packaging and cloud-layout behavior are pinned by `tests/test_pack_deploy.py` and `tests/test_preflight_cloud.py`; office-copy freshness is pinned by `_runtime/tests/test_office_template.py`. Root tests use `tests/_office_state.py` to skip only assertions invalidated by real ignored adapters on that machine, rather than contacting office services off-network. The FDC office adapters provide diagnosis scripts, not substitutes for contract tests.

### Frontend tests

`front-dev-home/package.json` uses Node's native test runner for colocated `app/**/*.test.ts` files:

```bash
cd front-dev-home
npm test
npm run typecheck
npm run lint
npm run build
```

Nuxt deliberately keeps test files inside Vue application typechecking: many tests import real composable row types and build snake_case fixtures, so typecheck guards frontend/backend response-shape drift. `@types/node` resolves `node:test` and `node:assert`, `allowImportingTsExtensions` supports explicit test imports, and CI uses Node 24 for native TypeScript stripping.

Recent implementation style deliberately extracts analytical logic into pure utilities before wiring Vue controls. Representative suites include:

- Device rules and drilldowns: `app/utils/ruleEngine.test.ts`, `deviceDrill.test.ts`
- Skewvoir: `app/utils/skewvoirAnalysis/*.test.ts`, `app/utils/anomaly/*.test.ts`, `overview.test.ts`
- Focus caching: `app/utils/skewvoirAnalysis/focusCache.test.ts`
- AFM: `afmExport.test.ts`, `afmHeatmap.test.ts`, `afmHistogram.test.ts`, `afmPointsTable.test.ts`
- Identity, recipe, roster, hardware, and live feeds: `identityInput.test.ts`, `identityDisplay.test.ts`, `recipeSearchMatch.test.ts`, `recipeSelection.test.ts`, `recipeView.test.ts`, `useRecipeParamDetail.test.ts`, `pendingToolMatrix.test.ts`, `toolType.test.ts`, `hardwareCompare.test.ts`, `fdcValues.test.ts`, `liveAlarm.test.ts`, `useLiveAlarmFeed.test.ts`
- Recipe-status analytics and exports: `recipeStatusTrend.test.ts`, `recipeStatusSummary.test.ts`, and `csvDownload.test.ts`; the six equipment Vue components currently have no component-specific automated tests, so verify line/bar switching, empty-state control disabling, filtered/sorted fleet rows, complete recipe-union export, active Align/Meas scoping, and no-execution blank rates in a browser check.
- Chat: `chatMarkdown.test.ts`, `relativeTime.test.ts`

## Frozen response fixtures

`scripts/capture_fixtures.py` captures representative mock responses, and `scripts/check_contract.py` compares a live server structurally with stored fixtures. The older fixture checker reports extra keys as potential contract changes, whereas the runtime TypedDict validator allows extras. Use both behaviors intentionally:

- TypedDict gate: provider compatibility and required shape.
- Fixture diff: reviewable notice that the public response surface changed.

These scripts expect a running backend and may assume port 5000; inspect their current arguments before use because home runtime now defaults to 5050.

## Current CI coverage

The active root workflow is `.github/workflows/ci.yml`. Its frontend job installs dependencies, runs Nuxt typecheck, and runs the Node tests. Its backend job runs `ruff check .` and the full `python -m pytest tests back_dev_home -q` suite on a clean checkout. Existing lint debt means ESLint is not currently an active root CI gate.

Ruff targets the office's minimum Python 3.11 and pins `E4`, `E7`, `E9`, `F`, and Bugbear `B` explicitly so a Ruff release cannot silently widen the gate. It excludes `ops_store`, `ftp_handler`, `minio_handler`, and `ops_index_mgmt` because they are confirmed or presumed vendored/shared trees; there is no formatter or import-sorting gate (`pyproject.toml`).

Not fully gated by active CI:

- frontend lint and build/generate;
- Markdown lint;
- fixture contract checks;
- browser/E2E flows;
- representative office-provider and deployment checks.

The scheduled OpenWiki workflow is documentation automation, not an application quality gate.

## Change-specific matrix

| Change area | Minimum focused verification |
| --- | --- |
| Flask app/auth/logging | App startup; `_auth` identity-chain, identify/verify/directory/admin tests; rate-limit, session/proxy, and error-handler regressions; identity input/display utilities; `_logging` middleware/handler/target suites; logging health route, activity/admin-log contracts, alias-provisioning guardrails, identity-source persistence, nonblocking drops, and endpoint-specific 503 behavior |
| Provider resolution/site detection | All `_runtime/tests`, health provider-route test, adapter-presence cascade, explicit-override refusal, boot table/reasons, stale-versus-edited classification, unknown-host mock fallback |
| Office adapter setup/sync | Setup/sync dry run, stub and edited-copy safeguards, stale backup, restart and health-provider verification |
| Provider implementation | Feature contract test under mock and office, route tests, representative real-source sample |
| API response | Contract test, fixture review, frontend typecheck and consuming workflow |
| Device Statistics | Recipe analytics and `test_oper_order.py`, rule engine/drill utilities, implemented bucket/skip semantics, lot/bucket URL flow, representative Redis/OpenSearch/MinIO office sample |
| Recipe/hardware operations | Recipe ranking/complete-fallback/source-capability; raw-path arithmetic, locator/path guards, raw route/normalization/align readers, row-keyed detail cache and grouped-layout tests; BM/PM and BSM office mappings, MDC/Reso Center reconstruction contracts, search-scoped hardware selection, SCE history, FDC parser tests, lateral measured-implies-ready consistency, representative office diagnosis |
| Recipe-status equipment analytics | Shared CSV/clipboard serializer and recipe-status utility tests; browser verification of grouped line/bar trends, filtered/sorted fleet export, complete recipe-union matrix export, active Align/Meas fail export, peer-signal suppression, empty-state disabling, and blank rates for equipment with no executions |
| Tool Roster / SEM list | Pending endpoint and office diff contract, NaN/blank normalization, loopback exclusion, model classification, fab/model matrix/drill-down, unique-IP/CSV export, route-entry cache behavior |
| Live alarm | Backend normalize/refresh/lock/board/roster/route/provider contracts; 20-minute window and multi-FAB worst-of/partial-configuration cases; frontend polling reducer, jitter, unread, and FAB-filter tests; representative office `fetched_at`, feed-status, and unmatched-roster checks |
| Skewvoir/MSR images | Meas-hist percentage and `eqp_ip` contracts, MSR detail and geometry round-trip tests, cursor/composite-selection/site-color/parameter-matrix utilities, FDC matrix/individual graph-selection reconciliation and parameter/all-axis restoration, chip/coordinate/mean correlation pairing, gallery scale/failure and no-download-all UI checks, image route/cache/memory+Redis job/FTP-template/scheduler/app-wiring suites, image-kind and wafer geometry/grid/axis utilities |
| Mag/Pixel and chart presentation | Mag/Pixel recommendation/FOV/orientation/assumption tests, gallery scale agreement, theme and palette suites, typecheck/build, browser checks for cleared fields, assumption badges, keyboard focus, linked highlights, matrix drill-down, and color-mode switching |
| Shared scheduler/deployment | All `_scheduler/tests`, jobs health endpoint, exact five-job KST roster, election/kill switch/locks/run log, `restart.txt`, four-process/four-thread/120-second uWSGI settings, plus `test_pack_deploy.py`, `test_preflight_cloud.py`, exact `/project/workSpace` layout, manifest and permissions review |
| AFM | AFM backend tests, pure heatmap/histogram/table/export tests, measurement-switch reset, image failure states |
| Chat | Route/store/LLM/config tests, `chat/tests/test_guard.py`, office blocked-host and `403 egress_blocked` behavior, Markdown and relative-time tests, retry/idempotency behavior |
| Nuxt config/build | Typecheck, test, lint, build or generate, offline icon rendering |
| Documentation | `npm run lint:md`, internal-link and source-reference review |

## Test design conventions

- Keep route tests focused on HTTP validation and response behavior.
- Put source-specific checks in provider tests and normalization contracts.
- Prefer pure TypeScript functions for data-heavy UI behavior; test them without mounting Vue where possible.
- Add regression tests for stale requests, rapid route changes, pagination reset, and large fan-out paths.
- Treat `NotImplementedError` as an expected migration signal only where explicitly documented; do not broadly swallow it.
- Keep official Skewvoir cohort tests separate from exploratory comparison-set behavior, following the [domain model](../domain/concepts.md#skewvoir-review-model).

## Gaps worth addressing

`ops_store`, `minio_handler`, and `ftp_handler` have no clear package-local test suites in the inspected tree. `ops_index_mgmt` has characterization coverage in `tests/test_vendored_ops_index_mgmt.py`, including logging-family aliases, mappings, lifecycle policy, and runtime-target agreement. Browser-level tests remain important for the `/identify` route/pill/release flow, URL-heavy analytical workflows, admin-log stale-row suppression, recipe fallback/raw-detail actions, FDC axis restoration, and hardware picker keyboard behavior.
