# Repository Guidelines

**Read [`CLAUDE.md`](CLAUDE.md) first.** It is the canonical agent guide for
this repo. It is written for Claude Code, but it binds every agent. This file
only adds what `CLAUDE.md` does not carry, and where the two disagree,
`CLAUDE.md` wins.

## Covered in CLAUDE.md

| Topic | `CLAUDE.md` section |
| --- | --- |
| Home / office / cloud phases, config-only switching | Three-Phase Deployment Strategy |
| Provider swap (`providers/office.py` vs `mock.py`; never edit `data.py`) | Architecture Patterns → API Abstraction Layer |
| Mock fidelity, `OFFICE-VERIFY`, datatables sync | Office DB knowledge lands in TWO places |
| Feature folders, blueprint auto-discovery, `contrib/` | Feature-sliced Backend Layout |
| `useAsyncData` caching, no Pinia, `usePersistedState` | Tech Stack |
| Colors and visual rules (`DESIGN.md`) | Visual language |
| Everyday run / test / lint commands | Commands |
| Rate limits, `LASTUSER` identity, pyarrow pool, scheduler | Runtime gotchas |
| Commit messages, explicit-path staging, worktrees | Development Notes → Git Workflow |
| Markdown lint, `MD060` compact tables, Korean docs | Markdown Notes |

## Key Paths

- `frontend/`: Nuxt 4 SPA. `app/pages/` routes, `app/components/`, `app/composables/`, `app/stores/` (`useState`-backed, not Pinia), `app/assets/css/`, `app/data/` (local reference content), `public/`.
- `backend/`: Flask API. The same code runs in every phase; only the adapter under each feature's `providers/` changes.
- `index.py` (repo root): WSGI entry exposing `app` and `application`; imports `create_app` from `backend`.
- `wsgi.ini` (repo root): uWSGI config (`module = index`, `callable = application`).
- `backend/health/`: health API, including `GET /api/health/providers`.
- `docs/`: teammate-facing documentation.
- Root `package.json`: Markdown lint tooling only; root `node_modules/` is required for `lint:md`.

## Setup and Extra Commands

The day-to-day commands are in `CLAUDE.md` → Commands. First-time setup and the
less common ones:

- Backend venv: CPython 3.11 at `.venv/`, matching the office interpreter. The
  home venv is uv-built and has no `pip`, so `.venv/bin/python -m pip` fails
  there. Create and fill it with
  `uv venv --python 3.11 .venv && uv pip install -r backend/requirements-dev.txt`.
  `requirements-dev.txt` adds pytest and ruff to `requirements.txt`, which stays
  test-free so the Phase 3 install ships no test runner.
- `uwsgi --ini wsgi.ini`: serve production-style.
- From `frontend/`: `npm run dev:remote` (bind `0.0.0.0`), `npm run build`
  (`nuxt generate`), `npm run preview`.
- From the repo root: `npm run lint:md:fix` auto-fixes supported Markdown issues.

Environment variables:

- `NUXT_API_TARGET`: where Nuxt proxies `/api/*`; defaults to `http://localhost:5050`.
- `NUXT_PUBLIC_API_BASE`: defaults to `/api`.
- `NUXT_PORT`: frontend dev port; default `3000`.
- `PORT`: Flask port; default `5050` because `5000` conflicts with macOS AirPlay.

## Coding Style

- Vue 3 + TypeScript with Nuxt file-based routing.
- ESLint via `@nuxt/eslint`; do not bypass lint failures. `frontend/nuxt.config.ts` enforces no trailing commas and `1tbs` braces.
- 2-space indentation; keep files formatter-friendly.
- Composables are `useXxx.ts`, stores are named by domain, components are PascalCase.
- In Flask, keep `routes.py` to routes and response behaviour; data access goes through the feature's `data.py` dispatcher.

## Testing

`.github/workflows/ci.yml` gates every push with two jobs: `lint + pytest` for
the backend, which runs `ruff check .` **before** pytest, and `typecheck + test`
for the frontend. The backend job's name says `lint` on purpose. While it was
called `pytest`, a ruff break that stopped pytest from ever running was reported
for a week as "pytest Failed". CI runs CPython 3.14; the home and office venvs
run 3.11. Frontend `npm run lint` is not gated yet because `main` still carries
pre-existing lint errors in untouched files.

- Office gate: after `cp backend/<feature>/providers/office_example.py backend/<feature>/providers/office.py`, run `SKEWNONO_<FEATURE>_PROVIDER=office .venv/bin/python -m pytest backend/<feature> -q`. Without the copy the run fails with a `RuntimeError` naming the exact `cp` command. It never falls back to mock silently, so a green run really did exercise the office adapter.
- Frontend tests use Node's built-in runner. The tree has no Vitest, Jest, jsdom, or `@vue/test-utils`, so only pure functions are covered. `@playwright/test` is a devDependency only because the Playwright MCP server needs it; it is not a suite.
- Colocate new tests: `X.test.ts` beside `X.ts`, and `backend/<feature>/tests/` beside the feature.

## Commits

This is a solo project developed on `main` with no pull requests, so the commit
body carries what a PR description would have: impacted routes or APIs,
environment variables, and phase-specific assumptions. Keep unrelated frontend,
backend, and docs changes in separate commits. Verify UI changes in the running
app before committing, following `.claude/skills/browser-verify/SKILL.md`,
because no reviewer downstream will catch a regression.
