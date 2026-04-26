# CLAUDE.md

## Project: SKEWNONO (스큐노노)

Web application for metrology, specified for tool management and data analytics.

## Three-Phase Deployment Strategy

### Phase 1 — Home / Offline
- Personal computer, fully offline
- Flask mock server (`back_dev_home/`) runs on `http://localhost:5000`
- Data sourced from in-memory Python mock modules (no OpenSearch, no Redis, no DB)
- Same Flask code and blueprint layout as Phase 2/3 — only the data-access layer differs
- Nuxt runs with `NUXT_API_TARGET=http://localhost:5000` so Nitro proxies `/api/*` to Flask

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
|-------|-----------|
| Frontend framework | Nuxt 3 + NuxtUI |
| State management | Pinia |
| Data fetching | TanStack Query (Vue Query) |
| Backend | Flask with Blueprints (auth, data, search, etc.) |
| Frontend serving (prod) | Flask serves built frontend files |

## Architecture Patterns

### Environment Switching
Three-tier configuration management. Database connections, API base URLs, and service configs change per environment. Frontend code stays the same across phases.

### API Abstraction Layer
- All phases: frontend calls Flask over `/api/*` via `$fetch`
- Swap surface is **inside each feature folder**: `back_dev_home/<feature>/data.py` (home mock) vs. a real implementation querying OpenSearch/Redis (office). Routes in `<feature>/routes.py` import via `from .data import ...` and do not change between phases.
- Blueprints and response shapes stay identical across phases
- Frontend code never branches on phase — only `NUXT_API_TARGET` changes

### Data Format Conventions
- Prefer **dict** and **dataframe dict** format (`dataframe.to_dict()`)
- Backend responses converted to dict/dataframe shape before returning JSON

### Feature-sliced Backend Layout
- Each Nuxt feature tab has a matching top-level folder under `back_dev_home/` (e.g. `sem_list/`, `tool_inventory/`).
- Each feature folder contains `routes.py` (the blueprint + handlers) and `data.py` (the data-access layer). Optional `__init__.py` re-exports `bp` for registration.
- `back_dev_home/_core/` holds cross-feature infrastructure (health check, shared utilities). Underscore prefix marks it as non-feature.
- `back_dev_home/__init__.py` is the app factory: it creates the Flask app, configures CORS, and registers each feature's blueprint under `/api`.
- Handlers depend only on data-access functions (e.g. `get_sem_list()`), never on DB drivers directly, so the home↔office swap is isolated to `<feature>/data.py`.

### Repository Layout
- `front-dev-home/` — Nuxt 3 SPA (same code runs in all phases; `ssr: false`)
- `back_dev_home/` — Flask mock backend for Phase 1; mirrors office Flask structure
- WSGI entry is root `index.py` (exposes `app` and `application`), which imports `create_app` from `back_dev_home`

## Development Notes

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
- Preferred format:

```md
| Column | Value |
| --- | --- |
| A | B |
```

- Avoid vertically aligned pipes or mixed table styles.
