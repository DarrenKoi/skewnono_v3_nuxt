---
name: home-to-office
description: Audit backend features against the mock→office provider convention before conveying work to the office. Use when the user says "office check", "sync check", "convey to office", "office 준비", or before /leave-office when backend changed.
argument-hint: [feature-name … | leave empty to auto-detect from git]
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

# Office Sync Check

Audit one or more `backend/` features against the provider convention
(rules: `docs/back-end/provider-selection.md`, adapter guidance:
`docs/back-end/office-data-adapters.md`, tool-family sub-adapters:
`docs/back-end/vendor-onboarding.md`)
so that everything created or modified at home is office-ready: folder
structure, contracts, gates, and the `MIGRATION.md` the office LLM works from.

## Provider file schema (home ↔ office)

The office adapter uses a **tracked template + gitignored real file** split so
home and office never author the same tracked file:

- `providers/office_example.py` — **tracked**, authored at home. The real
  adapter, implemented against `docs/datatables/` with unverified facts marked
  `OFFICE-VERIFY`. Home keeps this current as contracts evolve.
- `providers/office.py` — **gitignored** (`backend/**/providers/office.py`
  in the root `.gitignore`). Created at the office by
  `cp office_example.py office.py`, then corrected where the real source differs.
  Because it is untracked, `git pull` at the office never conflicts on it.

At home only the stub `office.py` may exist locally (untracked); a fresh clone
has none. Audit the **template**, not `office.py`.

## 1. Determine scope

- If arguments name features, audit those.
- **Skip `chat` — do not audit or flag it.** It has no `providers/` seam, and
  `docs/office-migration/STATUS.md` leaves it out on purpose. If it is named as
  an argument, say so and skip it; if auto-detection touches it, drop it silently.
- Otherwise auto-detect: `git status --porcelain` + `git diff HEAD~5 --name-only`,
  map touched files under `backend/<feature>/` to features (a route-owning
  folder = has `routes.py`). Also flag NEW route-owning folders that have no
  provider split at all — except under `backend/contrib/**`, which is
  office-only by design (`docs/contributing/in-repo/README.md`) and is
  skipped entirely.

## 2. Audit each feature (report table, one row per check)

| # | Check | How |
| --- | --- | --- |
| 1 | Folder layout | `contracts.py`, `data.py`, `MIGRATION.md`, `providers/mock.py`, `providers/office_example.py`, `tests/test_contract.py` all exist (NOT `office.py` — that is office-only) |
| 2 | Thin switch | `data.py` calls `get_data_provider("<key>")`; contains no data generation (no random/fixtures/loops building rows) |
| 3 | Routes discipline | `routes.py` imports only from `.data` (grep for `providers` imports — must be none) |
| 4 | Endpoint coverage | every `@bp.get/post/put/delete` in `routes.py` has a matching `## Endpoint:` block in `MIGRATION.md` |
| 5 | Contract coverage | every data function used by `routes.py` has an assert in `tests/test_contract.py`; tests import `from … import data`, never `providers.mock` (exception: mock-pin tests, e.g. msr_file) |
| 6 | Office template complete | every public function in `providers/mock.py` that `data.py` switches exists in `providers/office_example.py` with the same signature |
| 7 | Placeholders intact | `MIGRATION.md` still has `<!-- OFFICE: -->` slots for anything only knowable at the office |
| 8 | STATUS row | `docs/office-migration/STATUS.md` has a row with the feature's exact `get_data_provider` key as `SKEWNONO_<KEY>_PROVIDER` |
| 9 | Gate green | `.venv/bin/python -m pytest backend/<feature> -q` passes |
| 10 | Office switch wired | With no `providers/office.py`, `SKEWNONO_<KEY>_PROVIDER=office .venv/bin/python -m pytest backend/<feature> -q` fails with a `RuntimeError` naming the `cp` command — anything else means the switch is broken. Do not create `office.py` to run this check. |
| 11 | office.py untracked | `git check-ignore backend/<feature>/providers/office.py` matches, AND `git ls-files` does NOT list it — the real adapter must never be tracked |
| 12 | Sub-adapter folders | For every `providers/<sub>/` sub-folder (per-tab like `hardware/providers/fdc/`, or per tool family like `providers/veritysem/`): it has both `mock.py` and `office_example.py`, no tracked `office.py`, and the feature-level `providers/{mock,office_example}.py` still exist — moving those into a sub-folder erases the feature from `office_registry` |
| 13 | Sub-adapter dispatch | The feature-level dispatcher resolves sub-folders by name and guards on `exc.name`. Fallback policy must match the feature's kind: per-tab adapters fall back to that tab's mock, **tool-family adapters raise 501** — see `docs/back-end/vendor-onboarding.md` §3.4 |

## 3. Fix or report

- Auto-fix mechanical gaps after showing the user what's missing: create
  missing stubs/tests/MIGRATION blocks following the `activity` and `sem_list`
  exemplars (copy their file shapes exactly; derive contracts from mock output).
- Do not auto-edit `providers/mock.py` logic or `routes.py` — report only.
- Do not create or edit `providers/office.py` at home — it is office-only and
  gitignored. Author the skeleton in `providers/office_example.py` instead.
- New endpoints added to an existing feature: update `contracts.py` (new
  TypedDicts), add the contract test, add the MIGRATION.md endpoint block,
  extend `providers/office_example.py` with the new function.
  If a feature still has a tracked `providers/office.py`, migrate it:
  `cp office.py office_example.py && git rm --cached office.py`.
- Finish with `npm run lint:md` if any Markdown changed, and print a final
  READY / NOT READY verdict per feature with the office verify command:
  `SKEWNONO_<KEY>_PROVIDER=office .venv/bin/python -m pytest backend/<feature>`
