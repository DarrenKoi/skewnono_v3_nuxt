---
name: home-to-office
description: Audit backend features against the mock→office provider convention before conveying work to the office. Use when the user says "office check", "sync check", "convey to office", "office 준비", or before /leave-office when back_dev_home changed.
argument-hint: [feature-name … | leave empty to auto-detect from git]
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

# Office Sync Check

Audit one or more `back_dev_home/` features against the provider convention
(rules: `docs/back-end/provider-selection.md`, adapter guidance:
`docs/back-end/office-data-adapters.md`)
so that everything created or modified at home is office-ready: folder
structure, contracts, gates, and the GLM 5.2 prompt.

## Provider file schema (home ↔ office)

The office adapter uses a **tracked template + gitignored real file** split so
home and office never author the same tracked file:

- `providers/office_example.py` — **tracked**, authored at home. The skeleton
  (contract import + function signatures + `NotImplementedError` body + any
  `<!-- OFFICE: -->` markers). Home keeps this current as contracts evolve.
- `providers/office.py` — **gitignored** (`back_dev_home/*/providers/office.py`
  in the root `.gitignore`). Created at the office by
  `cp office_example.py office.py`, then implemented against the real source.
  Because it is untracked, `git pull` at the office never conflicts on it.

At home only the stub `office.py` may exist locally (untracked); a fresh clone
has none. Audit the **template**, not `office.py`.

## 1. Determine scope

- If arguments name features, audit those.
- **Deferred features — never audit, never flag:** `afm`, `skew`, `chat`. Their
  pages are hidden on the landing page and ship in the next SKEWNONO version, so
  they need no office adapter now. If one of them is named as an argument, say
  it is deferred and skip it; if auto-detection touches one, drop it silently.
  `docs/office-migration/STATUS.md` marks afm/skew `보류`; chat has no row at all,
  and that omission is intentional.
- Otherwise auto-detect: `git status --porcelain` + `git diff HEAD~5 --name-only`,
  map touched files under `back_dev_home/<feature>/` to features (a route-owning
  folder = has `routes.py`). Also flag NEW route-owning folders that have no
  provider split at all.

## 2. Audit each feature (report table, one row per check)

| # | Check | How |
| --- | --- | --- |
| 1 | Folder layout | `contracts.py`, `data.py`, `MIGRATION.md`, `providers/mock.py`, `providers/office_example.py`, `tests/test_contract.py` all exist (NOT `office.py` — that is office-only) |
| 2 | Thin switch | `data.py` calls `get_data_provider("<key>")`; contains no data generation (no random/fixtures/loops building rows) |
| 3 | Routes discipline | `routes.py` imports only from `.data` (grep for `providers` imports — must be none) |
| 4 | Endpoint coverage | every `@bp.get/post/put/delete` in `routes.py` has a matching `## Endpoint:` block in `MIGRATION.md` |
| 5 | Contract coverage | every data function used by `routes.py` has an assert in `tests/test_contract.py`; tests import `from … import data`, never `providers.mock` (exception: mock-pin tests, e.g. msr_file) |
| 6 | Office stub honest | every public function in `providers/mock.py` that `data.py` switches exists in `providers/office_example.py` (raising `NotImplementedError`) |
| 7 | Placeholders intact | `MIGRATION.md` still has `<!-- OFFICE: -->` slots for anything only knowable at the office |
| 8 | STATUS row | `docs/office-migration/STATUS.md` has a row with the feature's exact `get_data_provider` key as `SKEWNONO_<KEY>_PROVIDER` |
| 9 | Gate green | `.venv/bin/pytest back_dev_home/<feature> -q` passes |
| 10 | Office switch wired | `cp providers/office_example.py providers/office.py`, then `SKEWNONO_<KEY>_PROVIDER=office .venv/bin/pytest back_dev_home/<feature> -q` fails with NotImplementedError — anything else means the template/switch is broken. Leave the copied `office.py` in place (it is gitignored) or delete it after. |
| 11 | office.py untracked | `git check-ignore back_dev_home/<feature>/providers/office.py` matches, AND `git ls-files` does NOT list it — the real adapter must never be tracked |

## 3. Fix or report

- Auto-fix mechanical gaps after showing the user what's missing: create
  missing stubs/tests/MIGRATION blocks following the `activity` and `sem_list`
  exemplars (copy their file shapes exactly; derive contracts from mock output).
- NEVER auto-edit `providers/mock.py` logic or `routes.py` — report only.
- NEVER create or edit `providers/office.py` at home — it is office-only and
  gitignored. Author the skeleton in `providers/office_example.py` instead.
- New endpoints added to an existing feature: update `contracts.py` (new
  TypedDicts), add the contract test, add the MIGRATION.md endpoint block,
  extend `providers/office_example.py` with the new `NotImplementedError` stub.
  If a feature still has a tracked `providers/office.py`, migrate it:
  `cp office.py office_example.py && git rm --cached office.py`.
- Finish with `npm run lint:md` if any Markdown changed, and print a final
  READY / NOT READY verdict per feature with the office verify command:
  `SKEWNONO_<KEY>_PROVIDER=office .venv/bin/pytest back_dev_home/<feature>`
