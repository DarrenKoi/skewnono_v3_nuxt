---
type: Codebase Guide
title: SKEWNONO Repository Quickstart
description: Entry point for the SKEWNONO v3 codebase, covering its Nuxt and Flask runtime, metrology analytics and Mag/Pixel setup domains, local setup, engineering navigation, and current office-migration status.
resource: README.md
tags: [skewnono, quickstart, nuxt, flask, metrology]
---

# SKEWNONO repository quickstart

## What this repository is

SKEWNONO v3 is an internal E-Beam metrology operations and analytics platform. Its current product scope combines CD-SEM and HV-SEM equipment management, recipe and parameter governance, measurement review through Skewvoir, live failure alarms, an integrated but currently hidden AFM area, and supporting activity, access, API-token, and chat surfaces. The product overview targets roughly 320 CD-SEM/HV-SEM tools and emphasizes Tool-to-Tool Matching, reduced measurement TAT, and faster investigation of questionable measurements (`docs/project-overview.md`).

The active application is a client-only Nuxt 4 SPA backed by Flask. The [architecture](architecture/overview.md) keeps frontend calls stable at `/api/*` while each Flask feature selects mock or office data behind its `data.py` boundary. Home and unknown hosts default safely to mock mode; in office/cloud mode, a feature selects office data only when that machine has an ignored `providers/office.py`. Per-feature overrides remain authoritative, while `SKEWNONO_DATA_PROVIDER=mock` is a whole-instance kill switch.

## Start locally

Use the current code defaults rather than older README port examples.

```bash
# Backend, from the repository root
python -m venv .venv
.venv/bin/python -m pip install -r back_dev_home/requirements-dev.txt
PORT=5050 .venv/bin/python index.py

# Frontend, from front-dev-home/
npm ci
NUXT_API_TARGET=http://localhost:5050 npm run dev
```

Open `http://localhost:3000`. Nuxt proxies `/api/*` to Flask. On Windows PowerShell, use `.venv\Scripts\activate` and `npm.cmd` where execution policy blocks `npm.ps1`.

Minimum checks before submitting application changes:

```bash
# front-dev-home/
npm run typecheck
npm test
npm run lint
npm run build

# repository root
.venv/bin/ruff check .
.venv/bin/python -m pytest tests back_dev_home -q
npm run lint:md
```

See [operations](operations/runbook.md) for provider selection, production-style serving, and troubleshooting, and [testing guidance](testing/guidance.md) for the actual CI subset and contract gates.

## Runtime at a glance

```text
Nuxt page
  -> component/composable ($fetch, useAsyncData)
  -> /api through the Nitro development proxy
  -> Flask identity, access, logging, and rate-limit middleware
  -> auto-discovered feature Blueprint
  -> feature data.py dispatcher
  -> mock or office provider
  -> stable JSON contract
```

In production, Flask serves both `/api/*` and the generated SPA from `front-dev-home/.output/public`; there is no production Node server. The SPA therefore bundles fonts and icons for an offline internal network (`front-dev-home/nuxt.config.ts`).

## Where to go next

- [Architecture overview](architecture/overview.md) explains request flow, app composition, provider switching, authentication, logging, and deployment.
- [Domain concepts](domain/concepts.md) defines lots, recipes, measurement rules, review candidates, and the main product areas.
- [Key workflows](workflows/key-workflows.md) traces Device Statistics, Skewvoir, AFM, chat, and feature-extension paths through frontend and backend code.
- [Integration points](integrations/integration-points.md) separates live boundaries from planned OpenSearch, MinIO, FTP, office identity, and LLM integrations.
- [Operations runbook](operations/runbook.md) gives startup, safe office-adapter synchronization, cloud packaging/preflight, configuration, and failure-diagnosis guidance.
- [Testing guidance](testing/guidance.md) maps backend contract tests, frontend Node tests, fixture checks, and current CI gaps.
- [Source map](source-map.md) distinguishes active application code, support libraries, operational tooling, design evidence, and legacy AFM code.

## Engineering rules of thumb

1. Preserve API shapes. Reviewable adapter implementations and migration contracts belong in tracked `back_dev_home/<feature>/providers/office_example.py`; office-local copies and environment-specific details belong in gitignored `office.py`, whose presence enables that feature in office mode after restart. Use `scripts.setup_office_adapters`/`sync_office_adapters` so stub and locally edited copies are not overwritten blindly, then verify live selection through `/api/health/providers`, never through frontend phase branches.
2. Treat `contracts.py`, `docs/api-contracts/`, feature `MIGRATION.md` files, and frontend composables as a single boundary that must evolve together.
3. Use one `useAsyncData` key per shared frontend resource; do not introduce a second fetching framework without a demonstrated need.
4. Keep page-wide analysis state shareable in URL queries where the workflow is intended to be forwarded between engineers.
5. Distinguish official review state from exploratory comparisons; Skewvoir must not turn a user-curated set into an official assessment.
6. The standalone `afm_data_platform/` was removed after migration. Change AFM only in `front-dev-home/app/pages/afm/` and `back_dev_home/afm/`; use `docs/afm-migration-plan.md`, `docs/afm/`, and Git history for historical context.
7. Inspect recent git history for active areas. The July 2026 sequence moved computation into pure tested utilities, expanded office adapters and frontend analysis workflows, and replaced the tracked provider allowlist with machine-local adapter-presence discovery plus boot/health introspection.

## Known documentation drift

- Current home defaults are Flask `5050` (`index.py`) and Nuxt `3000` (`front-dev-home/nuxt.config.ts`); `wsgi.ini` listens on `5000`. Some READMEs still mention `3100` or `5000` for development.
- `front-dev-home/README.md` retains Nuxt starter-template material.
- `docs/development-workflow.md` describes an obsolete frontend mock-server switch. Current selection combines backend mode, machine-local `providers/office.py` presence, and optional feature overrides.

## Backlog

- **Office provider verification** — `docs/office-migration/STATUS.md` and feature `MIGRATION.md` files: the local contract baseline is green, but representative runs across the feature-level and nested office adapters remain on-site work. Use the setup/sync tools before verification, record contract and screen results in the ledger, and use `/api/health/providers` to confirm selection rather than readiness.
- **First cloud deployment** — `docs/deployment.md` and `scripts/deploy/`: overlay packaging and preflight are implemented and locally tested; build the SPA, run `python scripts/deploy/pack.py`, overlay the bundle without deleting permanent cloud-root `index.py`/`wsgi.ini`, then perform the first `/project/workSpace` feasibility deployment, permission restoration, `LASTUSER` forwarding check, and post-start identity/provider checks.
- **Live alarm office deployment** — `back_dev_home/ebeam/hitachi/live_alarm/MIGRATION.md`: copy the reader and portable writer office templates, register the writer on the external 15-second scheduler, and verify Redis heartbeat/feed status; mock API and UI behavior are implemented.
- **Rule persistence** — `back_dev_home/ebeam/cdsem/device_statistics/` and `useMeasurementRulesApi.ts`: implement save, history, rollback, and identity attribution after the datastore is chosen.
- **Measurement image office activation** — `back_dev_home/msr_image/MIGRATION.md`: the FTP adapter, rendered gallery/TIFF fallback, path guards, bounded jobs, and optional Redis shared state are implemented; create the ignored office copy, configure an isolated MinIO cache prefix and Redis for multi-worker use, then complete representative on-site FTP/cache verification.
- **AFM artifact source** — `back_dev_home/afm/providers/office_example.py`: decide whether large AFM bodies and images come from live source access, MinIO, or another service.
- **Operational hardening** — `back_dev_home/_runtime/env.py`, `back_dev_home/__init__.py`, and `wsgi.ini`: replace path-derived cloud detection; confirm the deployed nonblank secret, optional one-hop proxy trust, `LASTUSER` forwarding, and Redis-backed rate limiting under the real multi-worker topology.
- **Lower-priority surfaces** — PM planning and placeholder `thickness/`: documented only in the source map on this first pass; expand when those areas become the change target. Announcements now have a Redis office adapter with fail-open empty-banner behavior, but their user workflow remains intentionally brief here.
