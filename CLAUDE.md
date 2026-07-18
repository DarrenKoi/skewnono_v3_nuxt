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
| State management | Pinia (planned) + `useState` composables (current) |
| Data fetching | Nuxt `useAsyncData` + `$fetch` |
| Backend | Flask with Blueprints (auth, data, search, etc.) |
| Frontend serving (prod) | Flask serves built frontend files |

**Data fetching note:** Use `useAsyncData(key, fn)` for cached, deduplicated reads. Share one cache key per resource (e.g. `'sem-list'`) so multiple components reuse the same fetch — see `composables/useSemListApi.ts`'s `useSemList()` for the pattern. TanStack Query (Vue Query) is **not** used; introduce it only if you need TTL (`staleTime`), background refetch on focus, polling, or key-prefix invalidation — none of which apply to the current mock-data flows.

## Architecture Patterns

### Environment Switching
Three-tier configuration management. Database connections, API base URLs, and service configs change per environment. Frontend code stays the same across phases.

### API Abstraction Layer
- All phases: frontend calls Flask over `/api/*` via `$fetch`
- Swap surface is `back_dev_home/<feature>/providers/office.py` (fill in at the office) vs. `providers/mock.py` (home). `data.py` is a stable dispatcher that picks the adapter by env var — do **not** edit it. Routes import `from .data import ...` and never change between phases.
- Adapter selected at runtime by `SKEWNONO_<FEATURE>_PROVIDER` (e.g. `SKEWNONO_SEM_LIST_PROVIDER`) or global `SKEWNONO_DATA_PROVIDER`, values `mock`|`office`, default `mock`. Selector lives in `_runtime/data_provider.py`.
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
- Still only commit/push when I ask — working on `main` is not standing permission to commit unprompted.

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
