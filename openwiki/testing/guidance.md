---
type: Testing Guide
title: Testing and Quality Guidance
description: Test layers, commands, contract gates, fixture checks, CI coverage, and change-specific verification for the SKEWNONO Flask and Nuxt codebase.
resource: tests
tags: [testing, pytest, node-test, contracts, ci]
---

# Testing and quality guidance

## Test layers

The repository combines backend route/integration tests, feature-local provider contracts, and frontend pure-TypeScript tests. There is no single root command that runs every meaningful gate.

### Backend route and integration tests

Root tests under `tests/` use Flask clients and cover provider precedence, route filtering, response behavior, and office delegation. Runtime tests under `back_dev_home/_runtime/tests/` cover site detection and provider defaults. High-value suites include:

- `back_dev_home/_runtime/tests/test_site_provider.py`
- `test_access_control.py`
- `test_activity_home.py`
- `test_afm_home.py`
- `test_meas_hist_search_home.py` and `test_meas_hist_search_local.py`
- `test_msr_file.py`
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

.venv/bin/python -m back_dev_home.ebeam.hitachi.storage.providers.office
SKEWNONO_STORAGE_PROVIDER=office \
  .venv/bin/python -m pytest back_dev_home/ebeam/hitachi/storage -q
```

The smoke commands load `back_dev_home/.env` through shared Redis plumbing and use the package `-m` form required by imports. The contract gates allow an empty office fleet while deterministic mock gates require data; office verification must still use representative sources and the corresponding [workflow](../workflows/key-workflows.md).

Provider-default changes must also run `.venv/bin/python -m pytest back_dev_home/_runtime/tests/test_site_provider.py -q`. The invariant is that feature/global variables win, unknown and home hosts remain mock, and only `OFFICE_READY` features flip on recognized office/cloud sites. For Recipe TAT, test both the default ranked limit and `limit=0` (all buckets), plus lot-code bridge and empty-result behavior.

### Frontend tests

`front-dev-home/package.json` uses Node's native test runner for colocated `app/**/*.test.ts` files:

```bash
cd front-dev-home
npm test
npm run typecheck
npm run lint
npm run build
```

Nuxt excludes test files from Vue application typechecking because they import `node:test` and may use explicit `.ts` extensions. CI uses a Node version that supports native TypeScript stripping.

Recent implementation style deliberately extracts analytical logic into pure utilities before wiring Vue controls. Representative suites include:

- Device rules and drilldowns: `app/utils/ruleEngine.test.ts`, `deviceDrill.test.ts`
- Skewvoir: `app/utils/skewvoirAnalysis/*.test.ts`, `app/utils/anomaly/*.test.ts`, `overview.test.ts`
- Focus caching: `app/composables/useSkewvoirAnalysis.focusCache.test.ts`
- AFM: `afmExport.test.ts`, `afmHeatmap.test.ts`, `afmHistogram.test.ts`, `afmPointsTable.test.ts`
- Chat: `chatMarkdown.test.ts`, `relativeTime.test.ts`

## Frozen response fixtures

`scripts/capture_fixtures.py` captures representative mock responses, and `scripts/check_contract.py` compares a live server structurally with stored fixtures. The older fixture checker reports extra keys as potential contract changes, whereas the runtime TypedDict validator allows extras. Use both behaviors intentionally:

- TypedDict gate: provider compatibility and required shape.
- Fixture diff: reviewable notice that the public response surface changed.

These scripts expect a running backend and may assume port 5000; inspect their current arguments before use because home runtime now defaults to 5050.

## Current CI coverage

The active root workflow is `.github/workflows/ci.yml`. It installs frontend dependencies, runs Nuxt typecheck, and runs frontend Node tests. Existing lint debt means ESLint is not currently an active root CI gate.

Not fully gated by active CI:

- backend pytest suites;
- frontend lint and build/generate;
- Markdown lint;
- fixture contract checks;
- browser/E2E flows;
- operational support packages.

A workflow nested under `front-dev-home/.github/workflows/` is not loaded by GitHub for this repository. The scheduled OpenWiki workflow is documentation automation, not an application quality gate.

## Change-specific matrix

| Change area | Minimum focused verification |
| --- | --- |
| Flask app/auth/logging | App startup, relevant root tests, API-token/access tests, rate-limit and JSON 502/503 behavior |
| Provider resolution/site detection | `_runtime/tests/test_site_provider.py`, explicit override precedence, unknown-host mock fallback |
| Provider implementation | Feature contract test under mock and office, route tests, representative real-source sample |
| API response | Contract test, fixture review, frontend typecheck and consuming workflow |
| Device Statistics | Recipe analytics tests, rule engine/drill utility tests, lot/bucket URL flow |
| Skewvoir | Meas-hist/MSR backend tests, analysis/anomaly utilities, URL restoration, focus/set race behavior |
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

`ops_store`, `minio_handler`, `ftp_handler`, and `ops_index_mgmt` have no clear package-local test suites in the inspected tree. Before relying on them for office request paths, add transport fakes, normalization samples, timeout/failure tests, and safe integration checks. Browser-level tests are also important for the URL-heavy analytical workflows, but the first priority is bringing backend suites and production builds into active CI.
