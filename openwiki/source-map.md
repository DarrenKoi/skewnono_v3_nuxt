---
type: Source Map
title: Repository Source Map
description: Practical map of SKEWNONO active application code, feature domains, shared infrastructure, tests, operational tooling, design evidence, and historical or transitional modules.
resource: .
tags: [source-map, repository, navigation, modules]
---

# Repository source map

Use this map after reading the [quickstart](quickstart.md). It identifies ownership and runtime role rather than listing every file.

## Active application

| Path | Role | Start here when changing |
| --- | --- | --- |
| `index.py` | Flask development/WSGI entry | Process startup or port/bind behavior |
| `wsgi.ini` | uWSGI process/network configuration | Production-style process model |
| `back_dev_home/__init__.py` | App factory and Blueprint discovery | Middleware, feature registration, rate limiting |
| `back_dev_home/_runtime/` | Cloud and provider selection | Environment/data-source switching |
| `back_dev_home/_auth/` | SSO/local identity, tokens, admin/access middleware | Authentication and authorization |
| `back_dev_home/_logging/` | Request/activity and OpenSearch logging | Observability and usage semantics |
| `back_dev_home/_spa/` | Generated Nuxt SPA serving | Cloud static and fallback routes |
| `front-dev-home/nuxt.config.ts` | SPA, proxy, ports, offline assets, TS/lint config | Frontend runtime/build behavior |
| `front-dev-home/app/pages/` | Route-level product views | User navigation and page workflows |
| `front-dev-home/app/components/` | Reusable domain UI | Visual interaction changes |
| `front-dev-home/app/composables/` | API clients and shared state | Fetching, URL state, selection/caching |
| `front-dev-home/app/utils/` | Pure analysis and formatting logic | Testable computation |

The request path and change implications are detailed in [runtime architecture](architecture/overview.md).

## Backend feature domains

- `back_dev_home/ebeam/hitachi/`: shared CD-SEM/HV-SEM features such as storage and hardware.
- `back_dev_home/ebeam/cdsem/device_statistics/`: lot/recipe/parameter analytics and rule seed data.
- `back_dev_home/meas_hist/`: Skewvoir measurement discovery, search, facets, parent metadata, derived image-failure ratio, and equipment IP handoff.
- `back_dev_home/msr_file/`: detailed MSR rows, summaries, FDC/alignment, and geometry.
- `back_dev_home/msr_image/`: measurement-image listing/serving, safe async cache-fill jobs, memory/Redis job registries, disk/MinIO caches, purge scheduling, and a tracked tool-FTP adapter; Skewvoir consumes it, while local office activation and representative verification remain incomplete.
- `back_dev_home/afm/`: integrated AFM tools, files, detail, artifacts, and compatibility routes.
- `back_dev_home/chat/`: thread persistence and OpenAI-compatible completion boundary.
- `back_dev_home/activity/`, `access_control/`, `admin_logs/`, `api_tokens/`: shared user/admin operations.
- `back_dev_home/health/`: dependency-health reporting.
- `back_dev_home/sem_list/`: shared equipment list consumed across navigation/features.
- `back_dev_home/announcements/`, `device_statistics/`, `meas_hist/`, and other top-level folders: inspect exact route paths before assuming legacy versus active scope; some coexist with newer nested domains for compatibility.

Most provider-backed features follow `routes.py -> data.py -> providers/{mock,office}.py`, with `contracts.py`, tests, and sometimes `MIGRATION.md`. The [workflow guide](workflows/key-workflows.md) maps the highest-activity domains end to end.

## Frontend feature entrypoints

- `app/pages/ebeam/cd-sem/device-statistics/`: Device Statistics selection, comparison, profile, and rule editor.
- `app/pages/ebeam/*/skewvoir/`: measurement search and analysis; `app/components/ebeam/skewvoir/`, `useSkewvoirAnalysis.ts`, and `app/utils/skewvoirAnalysis/` hold its interaction, state, and pure analysis layers.
- `app/pages/mag-pixel.vue`: CD-SEM magnification/pixel reference and recommendation page; `app/components/magpixel/` renders guidance while `app/utils/magPixel.ts` owns FOV, resolution, and recommendation calculations shared with Skewvoir gallery calibration.
- `app/pages/afm/`: AFM hub, tool search, detail, and see-together.
- `app/pages/chat.vue`: conversational assistant.
- `app/pages/activity.vue`, `app/pages/admin/`, `app/pages/endpoints.vue`: usage, administration, and API-token documentation/management.
- `app/pages/ebeam/`: storage, hardware, recipe search/TAT, PM planning, fail/issues, and other E-Beam operations. CD-SEM/HV-SEM fab routes include the live-alarm board; its polling state lives in `useLiveAlarmFeed.ts`.
- `app/pages/thickness/`: emerging/placeholder equipment area; confirm implementation depth before extending.

## Data and integration support

| Path | Runtime classification | Purpose |
| --- | --- | --- |
| `ops_store/` | Shared transport library | Generic OpenSearch search/document/index operations |
| `minio_handler/` | Shared transport library | MinIO object, DataFrame, image, and presigned URL operations |
| `ftp_handler/` | Ingestion support | Direct/proxied fleet downloads and injected processing callbacks |
| `ops_index_mgmt/` | Operational tooling | OpenSearch templates, aliases, lifecycle policies, and migrations |
| `scripts/` | Engineering/operations helpers | Fixture/contract checks, office-adapter setup/sync, source diagnostics, and cloud packaging/preflight |

These packages [support office integrations](integrations/integration-points.md) but should not leak source-specific behavior into feature routes.

## Tests and contracts

- `tests/`: root Flask route/integration/provider-dispatch tests.
- `back_dev_home/**/tests/`: feature-local contracts and focused backend behavior.
- `front-dev-home/app/**/*.test.ts`: pure frontend tests run by Node.
- `docs/api-contracts/`: human-readable API schemas; useful primary evidence but verify against current routes/contracts.
- `back_dev_home/**/__fixtures__/`: frozen response structures where present.
- `.github/workflows/ci.yml`: active frontend typecheck/test and backend Ruff/full-pytest CI.

See [testing guidance](testing/guidance.md) before choosing a verification command.

## Design and historical evidence

- `CONTEXT.md`: shared metrology/domain language; use before changing business semantics.
- `docs/adr/`: durable product/architecture decisions such as lot-first analysis, shared audience URLs, and sampling design.
- `docs/project-overview.md`: product scope, equipment coverage, and roadmap.
- `docs/back-end/office-data-adapters.md`: office-provider boundary and migration guidance.
- `docs/deployment.md`: authoritative office-to-cloud packaging, transfer, preflight, permissions, and startup procedure.
- `docs/superpowers/specs/` and `plans/`: design rationale and implementation sequencing; many completed plans were recently pruned, so use git history when a deleted plan matters.
- `docs/handoff/`: recent work state for multi-step analyses.
- `AGENTS.md` and `CLAUDE.md`: development conventions; verify port/state details against code because parts have drifted.

Recent July 2026 history is especially relevant for AFM controls and exports, chat behavior/testing, Skewvoir analysis evolution, and provider/contract hardening. Use targeted `git log -- <path>` and `git show <commit> -- <path>` rather than reading old plans indiscriminately.

## Transitional and historical code

The standalone Flask/Vue `afm_data_platform/` was removed after its features were absorbed. The integrated AFM runtime lives in `back_dev_home/afm/`, `front-dev-home/app/pages/afm/`, `front-dev-home/app/components/afm/`, and `front-dev-home/app/utils/afm*.ts`; it [preserves migrated semantics](domain/concepts.md#afm) without a second frontend. `docs/afm-migration-plan.md` is the completed transition record, `docs/afm/` preserves the two source documents, and deleted implementation details are available through targeted Git history.

Other caution areas:

- `front-dev-home/README.md` still begins as a generic Nuxt starter.
- `docs/development-workflow.md` describes an obsolete Nuxt mock-server switch.
- Compatibility aliases and duplicate payload fields may remain intentionally during provider migration.
- Root `.remember/`, `.scratch/`, and generated planning material are process memory, issue tracking, or transient evidence, not runtime code.

## Navigation by change

- Product semantics: [domain concepts](domain/concepts.md) -> `CONTEXT.md` -> relevant ADR -> implementation.
- Request/data flow: [architecture](architecture/overview.md) -> composable -> route -> dispatcher -> provider.
- User behavior: [key workflows](workflows/key-workflows.md) -> route page and associated tests.
- External systems: [integration points](integrations/integration-points.md) -> office adapter and transport library.
- Startup/deployment: [operations runbook](operations/runbook.md) -> `index.py`, Nuxt config, `wsgi.ini`.
- Regression safety: [testing guidance](testing/guidance.md) -> focused tests -> broader gates.
