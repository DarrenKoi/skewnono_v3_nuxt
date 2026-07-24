# CLAUDE.md

## Project: SKEWNONO (스큐노노)

Web application for metrology, specified for tool management and data analytics.

## Three-Phase Deployment Strategy

### Phase 1 — Home / Offline
- Personal computer, fully offline
- Flask mock server (`back_dev_home/`) runs on `http://localhost:5050` (5000 conflicts with macOS AirPlay; `PORT` env overrides)
- Data sourced from in-memory Python mock modules (no OpenSearch, no Redis, no DB)
- Same Flask code and blueprint layout as Phase 2/3 — only the data-access layer differs
- Nuxt runs with `NUXT_API_TARGET=http://localhost:5050` so Nitro proxies `/api/*` to Flask

### Phase 2 — Company / Localhost
- Company infrastructure, localhost
- Flask dev server at `http://localhost:5000`

### Phase 3 — Company / Production
- Private cloud, internal network only
- Flask production server with internal URL
- Flask serves the built Nuxt frontend

**Cross-phase principle:** switch between mock → localhost → production via configuration changes only, no code changes.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend framework | Nuxt 4 + NuxtUI |
| State management | Nuxt `useState` composables + `usePersistedState` factory (no Pinia) |
| Data fetching | Nuxt `useAsyncData` + `$fetch` |
| Backend | Flask with Blueprints (auth, data, search, etc.) |
| Frontend serving (prod) | Flask serves built frontend files |

**Data fetching note:** Use `useAsyncData(key, fn)` for cached, deduplicated reads. Share one cache key per resource (e.g. `'sem-list'`) so multiple components reuse the same fetch — see `composables/useSemListApi.ts`'s `useSemList()` for the pattern. TanStack Query (Vue Query) is **not** used; introduce it only if you need TTL (`staleTime`), background refetch on focus, polling, or key-prefix invalidation — none of which apply to the current mock-data flows.

**State management note:** Pinia is **not** used — prefer Nuxt built-ins. Client state shared across pages lives in `useState`-backed composables; anything that must survive a full reload goes through `composables/usePersistedState.ts` (one `useState` ref + a detached-scope `flush: 'sync'` watcher persisting to localStorage — sync so an acknowledged click is durable even if the tab closes immediately). Do not hand-roll new localStorage read/write/watch plumbing in a composable; call `usePersistedState` instead. Revisit Pinia only if a real need appears (e.g. devtools time-travel debugging or cross-store orchestration that composables can't express cleanly).

## Architecture Patterns

### Environment Switching
Three-tier configuration management. Database connections, API base URLs, and service configs change per environment. Frontend code stays the same across phases.

### API Abstraction Layer
- All phases: frontend calls Flask over `/api/*` via `$fetch`
- Routes import `from .data import ...` and never change between phases. **One carve-out:** an endpoint that *reports on the swap mechanism itself* must not go through it — `/api/health/providers` reads `_runtime` directly, because a swappable introspection endpoint could misreport in exactly the situation you would query it.
- Swap surface is `back_dev_home/<feature>/providers/office.py` vs. `providers/mock.py` (home). `office.py` is **gitignored**; the tracked template is `providers/office_example.py` — implement/update the template, then `cp office_example.py office.py` at the office (office.py may carry 사내 schema details that stay out of git). `data.py` is a stable dispatcher that picks the adapter via `get_data_provider()` — do **not** edit it.
- Adapter selection is two independent questions. **Mode** — is this process at the office? — comes from `SKEWNONO_DATA_PROVIDER` (`mock`|`office`) when set, else from site detection (`_runtime/site.py`: the Phase 3 cloud deploy path via `is_cloud()`, or a `PC*` hostname, is office; home Mac mini and unknown hosts are home). **Readiness** — is this feature wired? — is whether `<feature>/providers/office.py` exists (`_runtime/office_registry.py`). A feature serves office data only when both hold, so **the `cp office_example.py office.py` that creates an adapter is the same act that switches it on** — there is no list to maintain. `SKEWNONO_<FEATURE>_PROVIDER` still overrides one feature either way; `=office` with no adapter present refuses to boot. `SKEWNONO_DATA_PROVIDER=mock` is a whole-instance kill switch. Inspect what actually resolved via `GET /api/health/providers` or the boot log.
- Because `office.py` is a copy, a `git pull` that moves `office_example.py` leaves the running adapter behind — it keeps serving 200s from old code. An office instance's boot log names any copy that is provably out of date (`STALE office.py: <feature> (copy of <sha>)`, from `_runtime/office_template.py`); refresh it with `python -m scripts.sync_office_adapters <feature>`. A copy carrying local 사내 changes is `EDITED`, never reported, and never overwritten without `--force`.
- Blueprints and response shapes stay identical across phases
- Frontend code never branches on phase — only `NUXT_API_TARGET` changes
- Exception: some features have more than one swap surface — `chat` swaps both storage and LLM config (env-driven), and file/image features (`msr_file`) also swap FTP/MinIO handlers. Check each feature's `MIGRATION.md`.

### Data Format Conventions
- Prefer **dict** and **dataframe dict** format (`dataframe.to_dict()`)
- Backend responses converted to dict/dataframe shape before returning JSON

### Feature-sliced Backend Layout
- Each Nuxt feature tab has a matching top-level folder under `back_dev_home/` (e.g. `sem_list/`, `tool_inventory/`).
- Each feature folder contains `routes.py` (blueprint), `contracts.py` (shared return type), `data.py` (env-var dispatcher), and `providers/{mock,office}.py` (adapters). Optional `__init__.py` re-exports `bp`. See `<feature>/MIGRATION.md` for what each office adapter needs.
- `back_dev_home/health/` owns the backend service health API. Add shared backend helpers only when a concrete feature needs them.
- `back_dev_home/__init__.py` is the app factory: it creates the Flask app, configures CORS, and registers each feature's blueprint under `/api`.
- Handlers depend only on data-access functions (e.g. `get_sem_list()`), never on DB drivers directly, so the home↔office swap is isolated to `providers/office.py`. Office adapters must normalize results to the `contracts.py` type — "resemble the mock" means match the contract shape, not the mock's data.

### Repository Layout
- `front-dev-home/` — Nuxt 4 SPA (same code runs in all phases; `ssr: false`)
- `back_dev_home/` — Flask mock backend for Phase 1; mirrors office Flask structure
- WSGI entry is root `index.py` (exposes `app` and `application`), which imports `create_app` from `back_dev_home`

## Development Notes

### Git Workflow
- **Work directly on `main` by default.** Commit and push to `main` unless I explicitly ask for a separate branch. Do **not** auto-create a feature branch just because the change lands on the default branch.
- **Commit and push whenever you judge it necessary** — no need to ask first. Use judgement: commit at coherent stopping points (a working feature, a passing test suite, a finished doc), not mid-edit.
- **Every commit message must say what changed.** Subject line in the existing `type(scope): summary` style, plus a body explaining what was updated and why when the change is not self-evident from the subject.

- Git-based workflow with separated workspaces per phase (home vs. office cannot sync directly)
- Flask backend is only accessible on company network
- Production secured within private cloud (no public internet exposure)
- Architecture prioritizes clean separation and maintainability over immediate feature complexity
- Extensible design: support incremental page/feature additions without major refactoring

## Playwright Screenshots

Save all Playwright MCP screenshots under `.playwright-mcp/screenshots/`. When calling `browser_take_screenshot`, always pass a relative `filename` like `.playwright-mcp/screenshots/<descriptive-name>.png` — the MCP server resolves relative paths from the project cwd, so omitting the prefix dumps PNGs at the repo root.

The `.playwright-mcp/` folder is already in `.gitignore`, so screenshots stay out of git automatically.

## Markdown Notes

- Run `npm run lint:md` after editing Markdown files.
- Use markdownlint `MD060` `compact` table style for every Markdown table.
- Write `docs/` and study Markdown in Korean when it is intended for teammate sharing.
- Use formal Korean sentence endings such as `~입니다.` and `~합니다.` consistently in those documents.

## Agent skills

### Issue tracker

Issues and specs are tracked as Markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Triage uses the five canonical label names as status values. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository with `CONTEXT.md` and `docs/adr/` at the root. See `docs/agents/domain.md`.

<!-- OPENWIKI:START -->

## OpenWiki

This repository uses OpenWiki for recurring code documentation. Start with `openwiki/quickstart.md`, then follow its links to architecture, workflows, domain concepts, operations, integrations, testing guidance, and source maps.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
