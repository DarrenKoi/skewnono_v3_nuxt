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
- All phases: frontend calls Flask over `/api/*` via `$fetch`. Blueprints and response shapes stay identical across phases, and frontend code never branches on phase — only `NUXT_API_TARGET` changes.
- Routes import `from .data import ...` and never change between phases.
- The swap surface is `providers/office.py` vs. `providers/mock.py`. **Do not edit `data.py`** — it is a stable dispatcher that picks the adapter via `get_data_provider()`. `office.py` is **gitignored**; the tracked template is `providers/office_example.py`, so you implement the template and `cp office_example.py office.py` at the office (the copy may carry 사내 schema details that stay out of git).
- Because `office.py` is a copy, a `git pull` that moves the template leaves the running adapter serving 200s from old code. The office boot log names any provably outdated copy (`STALE office.py: <feature>`); refresh with `python -m scripts.adapters.sync_office_adapters <feature>`.

Which adapter answers is the logical AND of two independent questions:

| Question | Meaning | Decided by |
| --- | --- | --- |
| Mode | Is this process at the office? | `SKEWNONO_DATA_PROVIDER`, else site detection (`_runtime/site.py`) |
| Readiness | Is this feature's adapter written? | Whether `<feature>/providers/office.py` exists |

So **the `cp` that creates an adapter is the same act that switches it on** — there is no activation list to maintain. `SKEWNONO_<FEATURE>_PROVIDER` overrides one feature either way (`=office` with no adapter refuses to boot); `SKEWNONO_DATA_PROVIDER=mock` is a whole-instance kill switch. Inspect what actually resolved via `GET /api/health/providers` or the boot log.

Full rules — site-detection order, the `/api/health/providers` carve-out, `EDITED` copies, the features with more than one swap surface (`msr_file`, `msr_image`) and the one that resolves on its own axis (`chat`, keyed on the `_rag` checkout), and the cross-feature pairings that must resolve together (`storage`'s office adapter joins against `sem_list`, so `validate_env()` refuses the mismatch at boot) — are in [`docs/back-end/provider-selection.md`](docs/back-end/provider-selection.md). Per-feature specifics live in each `<feature>/MIGRATION.md`.

### Office DB knowledge lands in TWO places, always

The office databases are unreachable from home, so **mock data is the only
carrier of what we know about them**. Whenever I tell you something new about an
office DB — a key name, an index alias, a field, a value convention, coverage,
a gotcha — update **both** of these in the same change:

1. `docs/datatables/<source>.txt` — the schema of record (see that folder's
   `README.md` for the file→source→feature map).
2. the feature's `providers/mock.py` — so home development is standing in for
   the real thing rather than drifting from it.

Updating only the doc is the failure mode to avoid: the doc is read when someone
writes an office adapter, but `mock.py` is what every home session actually runs
against. A fact recorded in one and not the other is a fact the next home session
will contradict.

"Update mock.py" usually means the **docstring** — what the mock stands in for,
and where it deliberately differs (grain, ranges, fabricated correlations).
Change generated values when the current ones would teach something false
about the real data.

**A mock resembles the real thing as closely as what we know allows.** Copy every
confirmed property — the shape of an identifier, which axes vary independently,
how wide the spread is, whether nulls appear — because a mock that is tidier than
the office is a mock that hides the office's bugs. Where the real value is
genuinely unknown, fabricate a plausible one and mark it `OFFICE-VERIFY`: the
provenance marks below are what separate a guess from a confirmed fact, so a
guess never has to be avoided, only labelled.

Where an office fact came from matters, so mark it: `office 확인 YYYY-MM-DD`
(verified by a real run), `user-confirmed`, or `OFFICE-VERIFY` (still an
assumption).

### Data Format Conventions
- Prefer **dict** and **dataframe dict** format (`dataframe.to_dict()`)
- Backend responses converted to dict/dataframe shape before returning JSON

### Feature-sliced Backend Layout
- Each Nuxt feature tab has a matching folder under `back_dev_home/`. Most are top-level (`sem_list/`, `msr_file/`, `msr_image/`, `afm/`, `meas_hist/`, `chat/`, …); the e-beam tabs sit **flat** under `ebeam/<feature>/` — `storage`, `tttm`, `recipe_tat`, `recipe_search`, `pm_planning`, `fail_issue`, `hardware`, `lateral_recipe`, `live_alarm`, `device_statistics`. **A page and its backend feature carry one name** (`/pm-planning` ↔ `pm_planning`, `/tttm` ↔ `tttm`, `/recipe-tat` ↔ `recipe_tat`): the page path is the feature slug with `-` for `_`, and `_logging/feature_map.py` files activity logs under that slug. Do not rename one side alone — the 2026-08-17 `pm-tune` detour cost a 47-file sweep to undo (2026-08-27); `/pm-tune` survives only as an identity alias there and in `utils/pageIdentity.ts`. There is **no vendor or tool-family folder in the path**: `_runtime/office_registry.py` identifies a feature by its directory name alone and refuses to boot on a duplicate, so `ebeam/amat/storage/` beside `ebeam/hitachi/storage/` is not untidy, it is an app that does not start.
- **Tool family is a `providers/` axis, never a path axis.** The registry of families (slug ↔ tool_type ↔ vendor ↔ adapter folder) is `back_dev_home/ebeam/_tool_specs.py`; a family-specific adapter goes under `<feature>/providers/<family>/`, the shape `hardware/providers/` already uses. Read [`docs/back-end/vendor-onboarding.md`](docs/back-end/vendor-onboarding.md) before wiring a new tool family into a feature — it carries the 8-step procedure and the reasons behind each rule.
- Underscore-prefixed folders (`_runtime/`, `_auth/`, `_core/`, `_logging/`,
  `_scheduler/`, `_spa/`) are shared plumbing, **not** features — the app
  factory skips them.
- Each feature folder contains `routes.py` (blueprint), `contracts.py` (shared return type), `data.py` (dispatcher), and `providers/{mock,office}.py` (adapters). Optional `__init__.py` re-exports `bp`. See `<feature>/MIGRATION.md` for what each office adapter needs. A feature whose home and office behaviour are the same code keeps `routes.py` and skips the rest — `chat`'s thread store is plain `chat/store.py`, so `chat` has no `providers/` and never appears in the provider table. Don't add a seam back until a second adapter actually exists.
- `back_dev_home/health/` owns the backend service health API. Add shared backend helpers only when a concrete feature needs them.
- `back_dev_home/__init__.py` is the app factory. Blueprints are **auto-discovered**: it rglobs for `routes.py`, skips any `_`-prefixed path, and registers each module's `bp` under `/api` — raising if a `routes.py` does not export a `Blueprint` named `bp`. Adding a feature means adding the folder; never edit the factory to register it.
- Handlers depend only on data-access functions (e.g. `get_sem_list()`), never on DB drivers directly, so the home↔office swap is isolated to `providers/office.py`. Office adapters must normalize results to the `contracts.py` type — "resemble the mock" means match the contract shape, not the mock's data.

### Repository Layout
- `front-dev-home/` — Nuxt 4 SPA (same code runs in all phases; `ssr: false`). Under `app/`: `pages/` (file-based routes), `components/`, `composables/`, `stores/` (`useState`-backed, not Pinia), `utils/`, `data/`, `assets/css/`.
- `back_dev_home/` — Flask mock backend for Phase 1; mirrors office Flask structure
- WSGI entry is root `index.py` (exposes `app` and `application`), which imports `create_app` from `back_dev_home`
- **`DESIGN.md` is the single source of truth for the frontend's visual language** — read it before any UI change. Colors come from `--sk-*` tokens only, never inline hex; where the code and `DESIGN.md` disagree, the code is what gets corrected.

## Commands

Backend, from the repo root (CPython 3.14 venv; no activation step needed):

```bash
.venv/bin/python index.py                              # Flask on :5050, hot-reloads at home
.venv/bin/python -m pytest -q                          # full suite (~3040 tests, ~115 s)
.venv/bin/python -m pytest back_dev_home/<feature> -q  # one feature
.venv/bin/python -m ruff check .                       # static gate, ~0.02 s — must be clean
```

(The device-statistics weekly-snapshot tests dominate that runtime: each one
builds a real 4000-lot payload. The suite has not rotted — that is where the
seconds go.)

Run pytest as `python -m pytest` from the root — `-m` is what puts the root on
`sys.path` so tests can import `back_dev_home.*`. The bare `-q` form and
`pytest tests back_dev_home -q` collect the same set (`testpaths` in
`pyproject.toml`); `tests/` **alone** silently skips every
`back_dev_home/**/tests/` provider-contract suite, which is the larger half and
the part that guards the mock→office swap.

Frontend, from `front-dev-home/`:

```bash
npm run dev        # Nuxt on :3000, Nitro proxies /api/* to :5050
npm test           # node --test over app/**/*.test.ts — pure functions only
npm run typecheck
npm run lint
```

From the repo root: `npm run lint:md` after any Markdown edit.

There is **no automated E2E suite** — no Playwright config, no spec files, and
no component tests (no mounting harness). Browser verification means driving
Playwright MCP by hand; see the `verify` skill.

### Runtime gotchas
- `/api/*` is rate-limited to 50 req / 5 s per user — space out curl loops or vary the identity. Three blueprints are exempt because one page view legitimately exceeds the budget: `msr_image` (gallery fan-out) and `fail_issue` + `recipe_tat` (the two behind `/recipe-status`). The list is `_EXEMPT_BLUEPRINTS` in `back_dev_home/__init__.py`.
- Identity at home is the `LASTUSER` cookie: `local-dev` = admin, digits = normal user, `X`-prefix = blocked by access control.
- `index.py` sets `ARROW_DEFAULT_MEMORY_POOL=system` before any import — **do not remove**. PyArrow 25's bundled mimalloc segfaults on macOS/Python 3.14 when a fresh thread first allocates, and the dev server runs every request on a fresh thread.
- Periodic jobs live in `back_dev_home/_scheduler/`, not in feature folders.
  Exactly one process runs them (uWSGI worker 1; the Werkzeug reloader's app
  child at home). `wsgi.ini`'s `lazy-apps` and `enable-threads` are
  load-bearing for this — see `docs/deployment.md`. Check runs with
  `GET /api/health/jobs`.

## Development Notes

### Git Workflow
- **Work directly on `main` by default.** Commit and push to `main` unless I explicitly ask for a separate branch. Do **not** auto-create a feature branch just because the change lands on the default branch.
- **Commit and push whenever you judge it necessary** — no need to ask first. Use judgement: commit at coherent stopping points (a working feature, a passing test suite, a finished doc), not mid-edit.
- **Every commit message must say what changed.** Subject line in the existing `type(scope): summary` style, plus a body explaining what was updated and why when the change is not self-evident from the subject.
- **Never stage broadly — commit only the files you personally edited.** Always pass explicit pathspecs: `git commit -- path/a path/b`, or `git add <exact paths>` followed by `git commit`. `git add -A`, `git add .`, `git commit -a`, and bare `git stash` are **banned**: I run several agent sessions against this one working tree, so a broad stage sweeps another session's half-finished edits into your commit under an unrelated subject line. Nothing errors — the log just gets corrupted. The same reason bans whole-tree `git checkout` / `git restore` / `git stash pop`.
- **Multi-file work goes in a `git worktree`.** If a task will touch more than a single file, create an isolated worktree first and do the whole change there, so concurrent sessions never share an index:

  ```bash
  git worktree add ../skewnono-<task> -b work/<task>   # from the repo root
  # ...edit, test, and commit inside ../skewnono-<task>...
  git -C . merge --ff-only work/<task> && git push      # back on main
  git worktree remove ../skewnono-<task> && git branch -d work/<task>
  ```

  This is the one sanctioned exception to "work directly on `main`" — the branch exists only to carry the worktree and is deleted on merge, so it is not a feature branch. Single-file edits stay in the main tree; the worktree setup is not worth it there.
- **Always tear the worktree down once the work is on `main`.** Merging and pushing is not the end of the task: run `git worktree remove` and `git branch -d` in the same session, immediately after the push succeeds. A task is only done when `git worktree list` shows the main tree alone. Leftover worktrees accumulate stale checkouts, hold onto merged branches, and mislead the next session about what work is still open.

- Git-based workflow with separated workspaces per phase (home vs. office cannot sync directly)
- Flask backend is only accessible on company network
- Production secured within private cloud (no public internet exposure)

### Deployment (Phase 3)

Pack at the office with `python scripts/deploy/pack.py` (after building the
frontend), then overlay the bundle contents onto the existing
`/project/workSpace/` on the cloud host. Do not replace that directory:
its permanent `index.py` and `wsgi.ini` are intentionally outside the bundle.
The path remains exact because `is_cloud()` is a filesystem check, not a config
flag. Full steps, including the bundle's `preflight.py`: `docs/deployment.md`.

## Playwright Screenshots

Save all Playwright MCP screenshots under `.playwright-mcp/screenshots/`. When calling `browser_take_screenshot`, always pass a relative `filename` like `.playwright-mcp/screenshots/<descriptive-name>.png` — the MCP server resolves relative paths from the project cwd, so omitting the prefix dumps PNGs at the repo root.

The `.playwright-mcp/` folder is already in `.gitignore`, so screenshots stay out of git automatically.

## Markdown Notes

- Run `npm run lint:md` after editing Markdown files. It covers the root `*.md`,
  `docs/`, `back_dev_home/` (the per-feature `MIGRATION.md` files), the top
  level of `scripts/` (its `README.md` holds the office-script rules) and
  `front-dev-home/` — every tree whose Markdown we author.
- Deliberately **not** linted, so do not widen the glob to reach them: vendored
  copies (`ftp_handler/`, `minio_handler/`, `ops_store/`, `ops_index_mgmt/`,
  `bento_agents.md`) must stay byte-identical to their upstream, `.remember/`,
  `.scratch/` and `.superpowers/` are scratch, and `.claude/skills/**` is
  agent-facing instruction text rather than teammate-facing docs.
- Use markdownlint `MD060` `compact` table style for every Markdown table.
- Write `docs/` and study Markdown in Korean when it is intended for teammate sharing.
- Use formal Korean sentence endings such as `~입니다.` and `~합니다.` consistently in those documents.

## Agent skills

### Project skills (`.claude/skills/`)

| Skill | Use for |
| --- | --- |
| `verify` | Launch/drive recipe for the running app (Flask + Nuxt), identities, browser checks |
| `home-to-office` | Audit features against the mock→office provider convention before conveying work |
| `generate-mock` | Scaffold a mock data composable for a new endpoint |
| `add-vendor` | Wire a new e-beam tool family (VeritySEM, Provision, …) into a feature — rules in `docs/back-end/vendor-onboarding.md` |

### Global skills that read this repo: the `oc-*` family

| Skill | Use for |
| --- | --- |
| `oc-review` | Two-axis review (Standards + Spec) of a diff, delegated to an opencode model, then reconciled against Claude's own reading |
| `oc-discuss` | Debate a decision with an opencode model over up to three rounds, ending in AGREED / DISPUTED / I-WAS-WRONG |

These two are installed **globally** at `~/.claude/skills/`, not in this
repo, so they work in any project. They share `~/.claude/skills/_opencode/`
(`oc.sh`, the tier table in `models.md`, the Fowler smell baseline, and the
logging format); that folder has no `SKILL.md`, so it is not itself a skill.

Everything SKEWNONO-specific they need lives in **`.claude/oc-project.md`** —
the escalation surfaces, the extra smells (mock/office formula drift and
friends), the constraints an outside model cannot infer,
the verify commands, and the logging destination. Keep it current the way
`CLAUDE.md` is kept current: the skills read it, and a stale overlay sends a
delegated reviewer at the wrong surfaces. The file's contract is
`~/.claude/skills/_opencode/project-overlay.md`.

Every `oc-*` run leaves a record under `docs/opencode/`; opencode always runs
read-only (`--agent plan`), so Claude applies any resulting edits.

### Issue tracker

Issues and specs are tracked as Markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Triage uses the five canonical label names as status values. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository with `CONTEXT.md` and `docs/adr/` at the root. See `docs/agents/domain.md`.
