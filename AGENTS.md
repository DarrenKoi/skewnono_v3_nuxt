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
- `front-dev-home/app/stores/`: shared client state. **Not Pinia** — Pinia is not
  a dependency of this project. `navigation.ts` is a `useState`-backed store in
  the Nuxt-built-ins style described in CLAUDE.md; anything that must survive a
  reload goes through `composables/usePersistedState.ts`.
- `front-dev-home/app/assets/css/`: global styles.
- `front-dev-home/public/`: static assets.
- `front-dev-home/app/data/`: local reference content used by the frontend.

Key backend paths:
- `index.py` (repo root): WSGI entry that exposes `app` and `application`; imports `create_app` from `back_dev_home`.
- `wsgi.ini` (repo root): uWSGI config (`module = index`, `callable = application`).
- `back_dev_home/__init__.py`: Flask app factory; registers each feature's blueprint under `/api`.
- `back_dev_home/health/`: service health API for backend dependencies.
- `back_dev_home/<feature>/routes.py`: blueprint + route handlers for one Nuxt-tab-aligned feature.
- `back_dev_home/<feature>/data.py`: stable dispatcher that picks the feature's adapter — do **not** edit it. The Phase 2/3 swap surface is `providers/office.py`; see `docs/back-end/provider-selection.md`.

## Deployment Phases
The repo is structured around configuration-only environment switching.

- Phase 1, home/offline: run `back_dev_home/` locally on `http://localhost:5050` with in-memory mock data.
- Phase 2, company/localhost: keep the same Flask API shape but swap to company-local data sources.
- Phase 3, company/production: Flask serves the built frontend and uses production infrastructure.

Cross-phase rule:
- Keep frontend API usage stable.
- Change configuration and backend data-access wiring, not frontend feature code.
- Preserve response shapes when replacing mock modules with real implementations.
- Make mock data resemble the office data as closely as what we know allows —
  identifier shape, which axes vary independently, spread, nulls. A mock tidier
  than the office hides the office's bugs. Fabricate what is genuinely unknown
  and mark it `OFFICE-VERIFY`.

## Build, Test, and Development Commands
Use the command set that matches the workspace you are editing.

Development happens on macOS: `npm` on PATH, and a CPython 3.14 virtualenv at
`.venv/` driven as `.venv/bin/python` (no activation step needed).

From the repo root:
- `npm install`: install repo-level Markdown tooling.
- `npm run lint:md`: lint Markdown files.
- `npm run lint:md:fix`: auto-fix supported Markdown issues.

From `front-dev-home/`:
- `npm install`: install frontend dependencies.
- `npm run dev`: start Nuxt at `http://localhost:3000`.
- `npm run dev:remote`: start Nuxt bound to `0.0.0.0`.
- `npm run build`: create a production build (`nuxt generate`).
- `npm run preview`: preview the production build.
- `npm run lint`: run ESLint.
- `npm run typecheck`: run Nuxt/Vue TypeScript checks.
- `npm test`: run the Node test runner over `app/**/*.test.ts`.

Backend (run from the repo root):
- `python3 -m venv .venv`: create a local virtual environment.
- `.venv/bin/python -m pip install -r back_dev_home/requirements.txt`: install Flask backend dependencies.
- `.venv/bin/python -m pip install -r back_dev_home/requirements-dev.txt`: same plus pytest, for running tests.
- `.venv/bin/python index.py`: start the Flask dev server on `http://localhost:5050`.
- `.venv/bin/python -m pytest tests back_dev_home -q`: run the backend test suite.
- `uwsgi --ini wsgi.ini`: serve via uWSGI (production-style).

Environment notes:
- `NUXT_API_TARGET` controls where Nuxt proxies `/api/*`; `nuxt.config.ts` already defaults it to `http://localhost:5050`, matching the home Flask port.
- `NUXT_PUBLIC_API_BASE` defaults to `/api`.
- `NUXT_PORT` overrides the frontend dev port; default is `3000`.
- `PORT` overrides the Flask port; the default is `5050` because `5000` conflicts with macOS AirPlay.

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
- Run `npm run lint:md` after editing Markdown files.
- Avoid markdownlint `MD060` by using the `compact` table style consistently.
- Write tables like `| Column | Value |` with delimiter rows like `| --- | --- |`.
- Do not vertically align pipes with extra hyphens or mix table styles in the same file.
- Write Markdown under `docs/` and teammate-facing study material in Korean when it is meant for internal sharing.
- In those documents, use formal sentence endings such as `~입니다.` and `~합니다.` consistently.

## Testing Guidelines
Both workspaces have a working test runner, and `.github/workflows/ci.yml` gates
both on every push: a `pytest` job for the backend and a `typecheck + test` job
for the frontend. `npm run lint` is deliberately not gated yet, because `main`
still carries pre-existing lint errors in untouched files.

Backend — pytest on CPython 3.14, installed from `back_dev_home/requirements-dev.txt`
(kept out of `requirements.txt` so the Phase 3 production install ships no test
runner). Always run from the repo root, in the `python -m pytest` form: `-m` is
what puts the repo root on `sys.path` so tests can import `back_dev_home.*`.

- `.venv/bin/python -m pytest tests back_dev_home -q`: the whole backend suite (~2090 tests, ~9 s). Both roots matter — `tests/` holds the cross-feature Flask suites, and `back_dev_home/**/tests/` holds the per-feature provider contract suites, which are the larger half and the part that guards the mock→office swap.
- `.venv/bin/python -m pytest -q`: identical collection. Root `pyproject.toml` sets `testpaths = ["tests", "back_dev_home"]`, so the bare form and the explicit one are interchangeable.
- `.venv/bin/python -m pytest back_dev_home/<feature> -q`: one feature, against whichever provider currently resolves (mock at home).
- `SKEWNONO_<FEATURE>_PROVIDER=office .venv/bin/python -m pytest back_dev_home/<feature> -q`: the Phase 2 office gate. Run it at the office after `cp back_dev_home/<feature>/providers/office_example.py back_dev_home/<feature>/providers/office.py`. Without that copy the run fails loudly with a `RuntimeError` naming the exact `cp` command — it never silently falls back to mock, so a green run really did exercise the office adapter.

Frontend — Node's built-in test runner (`node --test "app/**/*.test.ts"`). There
is no Vitest, Jest, jsdom, or `@vue/test-utils` in the tree.

- `npm test` from `front-dev-home/`: colocated `*.test.ts` files next to the code they cover.
- `npm run typecheck` and `npm run lint` remain the other frontend gates.
- Only pure functions are covered. Without a mounting harness, `.vue` components have no unit tests, and there is **no automated E2E suite** — no Playwright config and no spec files exist. `@playwright/test` is present only as a devDependency behind the Playwright MCP server, which is an interactive tool a developer or agent drives by hand, not a suite CI can run.

Other notes:

- For docs-only changes, rerun `npm run lint:md` from the repo root.
- Colocate new tests with the code they cover: `X.test.ts` beside `X.ts`, and `back_dev_home/<feature>/tests/` beside the feature.

## Commit Guidelines

This is a solo project developed directly on `main`: no pull requests, no
feature branches (see CLAUDE.md's Git Workflow). Everything a PR description
would have carried goes in the commit body instead, because the commit log is
the only record anyone reads later.

- Subject line in the existing `type(scope): summary` style, scoped to one change.
- Add a body whenever the subject alone is not self-evident, covering what changed and why. Impacted routes or APIs, environment variables, and phase-specific assumptions belong here.
- Keep commits reviewable: avoid mixing unrelated frontend, backend, and docs changes unless they are part of the same feature.
- Verify UI changes in the running app before committing — see the `verify` skill. There is no reviewer downstream to catch a regression.

### Staging and isolation (several sessions share one tree)

More than one agent session usually runs against this single working tree, so
staging is not a private act — a broad stage picks up whatever another session
has mid-edit.

- **Stage only the files you edited yourself, by explicit path**: `git commit -- path/a path/b`, or `git add <exact paths>` then `git commit`.
- **Banned outright**: `git add -A`, `git add .`, `git commit -a`, bare `git stash`, and whole-tree `git checkout` / `git restore`. These fail silently rather than loudly — the commit succeeds and carries someone else's unfinished work.
- **Touching more than one file? Work in a `git worktree`** so your index is your own:

  ```bash
  git worktree add ../skewnono-<task> -b work/<task>
  # edit / test / commit inside ../skewnono-<task>
  git merge --ff-only work/<task> && git push      # back in the main tree
  git worktree remove ../skewnono-<task> && git branch -d work/<task>
  ```

- **Remove the worktree as soon as the work is pushed to `main`** — the last two commands above are part of the task, not cleanup for later. Confirm with `git worktree list` that only the main tree remains.
- `work/<task>` is scaffolding for the worktree, not a feature branch; it is deleted on merge, so this does not contradict "developed directly on `main`" above.

<!-- OPENWIKI:START -->

## OpenWiki

This repository uses OpenWiki for recurring code documentation. Start with `openwiki/quickstart.md`, then follow its links to architecture, workflows, domain concepts, operations, integrations, testing guidance, and source maps.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
