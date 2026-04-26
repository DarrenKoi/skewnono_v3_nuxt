# Repository Guidelines

## Project Structure & Architecture
This repository now follows the two-app plan described in `CLAUDE.md`.

- `front-dev-home/`: Nuxt frontend workspace. The app currently runs on Nuxt 4 with `@nuxt/ui`, `ssr: false`, and a Nitro dev proxy that forwards `/api/*` to `NUXT_API_TARGET`.
- `back_dev_home/`: Flask mock backend for the home/offline phase. It mirrors the office backend shape so the frontend can keep the same API contract across environments.
- `docs/`: shared documentation and teammate-facing Markdown.
- root `package.json`: repo-level Markdown lint tooling. Root `node_modules/` is still required for `lint:md`.

Key frontend paths:
- `front-dev-home/app/pages/`: route-driven views.
- `front-dev-home/app/components/`: reusable UI components.
- `front-dev-home/app/composables/`: shared Composition API logic.
- `front-dev-home/app/stores/`: Pinia stores.
- `front-dev-home/app/assets/css/`: global styles.
- `front-dev-home/public/`: static assets.
- `front-dev-home/app/mock-data/`: local reference content used by the frontend.

Key backend paths:
- `index.py` (repo root): WSGI entry that exposes `app` and `application`; imports `create_app` from `back_dev_home`.
- `wsgi.ini` (repo root): uWSGI config (`module = index`, `callable = application`).
- `back_dev_home/__init__.py`: Flask app factory; registers each feature's blueprint under `/api`.
- `back_dev_home/_core/`: cross-feature infrastructure (health check, shared utilities).
- `back_dev_home/<feature>/routes.py`: blueprint + route handlers for one Nuxt-tab-aligned feature.
- `back_dev_home/<feature>/data.py`: data-access layer for that feature — Phase 1 mock, swapped for a real implementation in Phase 2/3.

## Deployment Phases
The repo is structured around configuration-only environment switching.

- Phase 1, home/offline: run `back_dev_home/` locally on `http://localhost:5000` with in-memory mock data.
- Phase 2, company/localhost: keep the same Flask API shape but swap to company-local data sources.
- Phase 3, company/production: Flask serves the built frontend and uses production infrastructure.

Cross-phase rule:
- Keep frontend API usage stable.
- Change configuration and backend data-access wiring, not frontend feature code.
- Preserve response shapes when replacing mock modules with real implementations.

## Build, Test, and Development Commands
Use the command set that matches the workspace you are editing.

From the repo root:
- `npm.cmd install`: install repo-level Markdown tooling on this Windows setup.
- `npm.cmd run lint:md`: lint Markdown files.
- `npm.cmd run lint:md:fix`: auto-fix supported Markdown issues.

From `front-dev-home/`:
- `npm.cmd install`: install frontend dependencies.
- `npm.cmd run dev`: start Nuxt at `http://localhost:3100`.
- `npm.cmd run dev:remote`: start Nuxt bound to `0.0.0.0`.
- `npm.cmd run build`: create a production build.
- `npm.cmd run preview`: preview the production build.
- `npm.cmd run lint`: run ESLint.
- `npm.cmd run typecheck`: run Nuxt/Vue TypeScript checks.

Backend (run from the repo root):
- `python -m venv .venv`: create a local virtual environment.
- `.venv\Scripts\activate`: activate the virtual environment in PowerShell.
- `python -m pip install -r back_dev_home/requirements.txt`: install Flask backend dependencies.
- `python index.py`: start the Flask dev server on `http://localhost:5000`.
- `uwsgi --ini wsgi.ini`: serve via uWSGI (production-style).

Environment notes:
- `NUXT_API_TARGET` controls where Nuxt proxies `/api/*`; default is `http://localhost:5000`.
- `NUXT_PUBLIC_API_BASE` defaults to `/api`.
- `NUXT_PORT` overrides the frontend dev port; default is `3100`.
- On this Windows machine, prefer `npm.cmd` over `npm` in PowerShell because `npm.ps1` may be blocked by execution policy.

## Coding Style & Naming Conventions
- Use Vue 3 + TypeScript patterns with Nuxt file-based routing in `front-dev-home/`.
- Follow ESLint via `@nuxt/eslint`; do not bypass lint failures.
- `front-dev-home/nuxt.config.ts` enforces no trailing commas and `1tbs` brace style.
- Prefer 2-space indentation and keep files formatter-friendly.
- Name composables as `useXxx.ts`, stores by domain, and Vue components in PascalCase.
- Keep route files descriptive and colocated by feature.
- For cached frontend reads, use Nuxt's `useAsyncData(key, fn)` and share one key per resource (see `composables/useSemListApi.ts` `useSemList()`). TanStack Query (Vue Query) is not used in this project — Nuxt's built-in caching covers our needs.
- In Flask, keep `routes.py` focused on route and response behavior. The environment swap should happen in each feature's `data.py`, not inside route handlers.
- Preserve API response shapes when moving from mock data to real backends.

## Markdown Conventions
- Run `npm.cmd run lint:md` after editing Markdown files.
- Avoid markdownlint `MD060` by using the `compact` table style consistently.
- Write tables like `| Column | Value |` with delimiter rows like `| --- | --- |`.
- Do not vertically align pipes with extra hyphens or mix table styles in the same file.
- Write Markdown under `docs/` and teammate-facing study material in Korean when it is meant for internal sharing.
- In those documents, use formal sentence endings such as `~입니다.` and `~합니다.` consistently.

## Testing Guidelines
There is no dedicated unit or E2E runner configured at the repo root yet.

- Frontend minimum quality gate: `npm.cmd run lint` and `npm.cmd run typecheck` from `front-dev-home/`.
- Backend changes should be verified by running the Flask server and checking the affected `/api/*` routes directly.
- For docs-only changes, rerun `npm.cmd run lint:md`.
- When adding tests later, colocate them near the feature they cover and keep them focused on critical UI logic, composables, stores, or backend route behavior.

## Commit & Pull Request Guidelines
- Use short, imperative commit messages scoped to one change.
- Keep commits reviewable and avoid mixing unrelated frontend, backend, and docs changes unless they are part of the same feature.
- PRs should state purpose, key changes, impacted routes or APIs, and manual verification steps.
- Include screenshots or recordings for UI changes.
- Note any environment variables or phase-specific assumptions when relevant.
