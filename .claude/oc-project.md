# oc-* project overlay

Read by the globally-installed `oc-review`, `oc-simplify`, and `oc-discuss`
skills (`~/.claude/skills/`). The skills themselves are project-agnostic; every
SKEWNONO-specific fact they need is here. The file's contract is
`~/.claude/skills/_opencode/project-overlay.md`.

Keep this current the same way `CLAUDE.md` is kept current — a stale overlay
sends a delegated reviewer looking at the wrong surfaces.

## Standards sources

Most authoritative first:

1. `CLAUDE.md` — the project rules, including the provider convention and the
   staging discipline
2. `DESIGN.md` — **single source of truth for the frontend visual language**.
   Colors come from `--sk-*` tokens only, never inline hex. Where the code and
   `DESIGN.md` disagree, the code is what gets corrected
3. `<feature>/MIGRATION.md` — per-feature office-adapter requirements, for any
   backend feature folder the diff touches
4. `docs/back-end/provider-selection.md` — the full mode/readiness rules

## Escalation surfaces

Move up one tier when the diff touches these, regardless of size. The reason is
the same in every case and is what generalises: **the home test suite passes
either way**, because the office databases are unreachable from home. A missed
finding here does not fail on this machine — it fails at the office, on a later
trip.

- `**/providers/` — the mock↔office swap surface. `office.py` is a gitignored
  `cp` of `office_example.py`, so a fix applied to one copy is not applied to
  the other
- `**/contracts.py` — the shared return type both adapters must satisfy
- `back_dev_home/_runtime/` — site detection, provider registry, Redis plumbing;
  a mistake here mis-routes *every* feature at once
- `docs/datatables/` — the schema of record for the office DBs. It is read when
  someone writes an office adapter, so a wrong line here is wrong for months
- `scripts/deploy/` and `wsgi.ini` — only exercised on the cloud host

## Extra smells

Appended to the Fowler baseline verbatim. These are SKEWNONO failure modes the
generic list does not name:

- **Mock/office formula drift** — a guard, clamp, or derived-value rule added to `providers/mock.py` but not to the sibling `providers/office_example.py` (or vice versa). Home tests pass; the office silently computes a different answer. → grep the sibling for the same expression.
- **Unmarked office assumption** — a value in a mock presented as fact when nobody has confirmed it against a real office DB. → mark it `OFFICE-VERIFY`, or cite `office 확인 YYYY-MM-DD` / `user-confirmed`.
- **Doc/mock split** — a new office-DB fact recorded in `docs/datatables/<source>.txt` but not in the feature's `mock.py`, or the reverse. Both must change together.
- **Value-domain narrowing** — a mock that never emits `None`, `NaN`, `NaT`, or an empty frame, so every null-handling path in the office adapter is untested at home.
- **Vendor folder in a feature path** — an `ebeam/<vendor>/<feature>/` directory. Tool family is a `providers/` axis, never a path axis; a duplicate feature slug makes the app factory refuse to boot. → `<feature>/providers/<family>/`.
- **Hand-rolled localStorage plumbing** — a composable doing its own read/write/watch instead of calling `composables/usePersistedState.ts`.
- **Inline hex or raw Tailwind color** in a Vue file where a `--sk-*` token exists.

## Deliberate structure

Pasted verbatim into the `oc-simplify` prompt. An over-engineering lens run
cold tags these `yagni:` or `delete:`; each exists on purpose, and `CLAUDE.md`
or `DESIGN.md` says why:

- **The provider seam looks single-implementation at home.** `office.py` is a
  gitignored `cp`, so at home `<feature>/data.py` dispatches to
  `providers/mock.py` alone and `contracts.py` binds one adapter. The second
  implementation exists at the office; `data.py` is never edited
- **`providers/office_example.py` is unused at home by design.** It is the
  tracked template for the gitignored `office.py`, not dead code
- **`__fixtures__/` directories are load-bearing.** Captured office responses a
  contract test replays; a feature-scoped scan finds no importer
- **Provider env knobs are unset at home on purpose.** `SKEWNONO_DATA_PROVIDER`,
  `SKEWNONO_<FEATURE>_PROVIDER`, and the office-source knobs configure the
  office, they are not "config nobody sets"
- **Identity aliases stay.** `/pm-tune` in `_logging/feature_map.py` and
  `utils/pageIdentity.ts` keeps logged history readable; it is not a duplicate
  route
- **NuxtUI `U*` components and `--sk-*` tokens are the documented standard**
  (`DESIGN.md`). A `native:` finding that swaps them for raw HTML controls or
  inline CSS is a Standards breach, not a simplification
- **Vendored trees are out of scope** — `ftp_handler/`, `minio_handler/`,
  `ops_store/`, `ops_index_mgmt/` must stay byte-identical to their upstream
  (change both or neither), so no `shrink:` or `stdlib:` there

## Reuse hotspots

Grep these before accepting any "this is new" claim:

- `back_dev_home/_runtime/`, `_core/`, `_auth/`, `_logging/` — shared backend plumbing
- `front-dev-home/app/utils/` and `app/composables/` — shared frontend logic
- `front-dev-home/app/assets/css/main.css` — the `--sk-*` tokens and `sk-*` classes
- `back_dev_home/ebeam/_tool_specs.py` — the tool-family registry

## Spec source

Issues and specs are Markdown under `.scratch/`, per
`docs/agents/issue-tracker.md`. Look in this order: issue references in the
commit messages, `.scratch/<topic>/spec.md`, then `docs/` matching the branch
name, then ask.

## Constraints an outsider cannot infer

State these in any `oc-discuss` round 1, or the model spends it on ruled-out advice:

- **The office databases are unreachable from home** (proven, not assumed). Any
  advice that ends in "check the real data" is unactionable in a home session
- **Pinia is not used.** State is `useState` composables plus
  `usePersistedState`. So is TanStack Query — `useAsyncData` + `$fetch` only
- **The working tree is shared across several concurrent agent sessions.** This
  is why broad staging is banned, not tidiness
- **There is no automated E2E suite** — no Playwright config, no component
  tests. "Add an E2E test" is a project, not a step
- **Nuxt runs `ssr: false`.** Hydration-mismatch reasoning does not apply
- **Production is http-only** on an internal network. Secure-context browser
  APIs (`crypto.randomUUID`) are unavailable there
- **`office.py` is gitignored**, so it is absent in a fresh `git worktree` and
  test skip counts legitimately differ from the main checkout

## Logging

- Destination: `docs/opencode/YYYY-MM-DD-<short-kebab-title>.md`
- Language: Korean, formal endings (`~입니다.`, `~합니다.`), markdownlint
  `MD060` compact tables. The model's own findings stay **verbatim** in whatever
  language they came back in
- Lint after writing: `npm run lint:md` from the repo root

## Verify commands

From the repo root (CPython 3.14 venv, no activation step):

```bash
.venv/bin/python -m ruff check .                          # static gate, ~0.02s, must be clean
.venv/bin/python -m pytest back_dev_home/<feature> -q     # one feature
.venv/bin/python -m pytest -q                             # full suite, ~3040 tests, ~115s
```

Run pytest as `python -m pytest` from the root — `-m` is what puts the root on
`sys.path`. `pytest tests/` **alone** silently skips every
`back_dev_home/**/tests/` provider-contract suite, which is the half that guards
the mock→office swap.

Frontend, from `front-dev-home/`: `npm test`, `npm run typecheck`, `npm run lint`.

`.venv/` and `node_modules/` are gitignored and therefore **absent in a fresh
worktree**. Run them from the main checkout, or point at its interpreter
(`/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python`), rather than
concluding the tooling is broken.

## Commit rules

Per `CLAUDE.md`:

- Work directly on `main`; commit and push without asking at coherent stopping
  points
- **Explicit pathspecs only.** `git add -A`, `git add .`, `git commit -a`, and
  bare `git stash` are banned — concurrent sessions share this working tree, so
  a broad stage sweeps another session's half-finished edits into your commit
  under an unrelated subject line
- Multi-file work goes in a `git worktree`, torn down in the same session once
  the work is merged and pushed
