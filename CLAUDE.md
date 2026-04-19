# CLAUDE.md

## Project: SKEWNONO (스큐노노)

Web application for metrology, specified for tool management and data analytics.

## Three-Phase Deployment Strategy

### Phase 1 — Home / Offline
- Personal computer, fully offline
- No backend server; all data via JS/TS mock data
- Mock layer mimics the fetch API so it can be swapped for real calls later

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
- Phase 1: mock data modules that return promises (mimicking fetch API)
- Phase 2/3: real fetch calls to Flask endpoints
- Swap via config, not code changes

### Data Format Conventions
- Prefer **dict** and **dataframe dict** format (`dataframe.to_dict()`)
- Backend responses converted to dict/dataframe shape before returning JSON

### Flask Blueprints
- Modular API organization (auth, data, search, etc.)
- RESTful endpoint design
- Each blueprint can be developed independently

## Development Notes

- Git-based workflow with separated workspaces per phase (home vs. office cannot sync directly)
- Flask backend is only accessible on company network
- Production secured within private cloud (no public internet exposure)
- Architecture prioritizes clean separation and maintainability over immediate feature complexity
- Extensible design: support incremental page/feature additions without major refactoring

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
