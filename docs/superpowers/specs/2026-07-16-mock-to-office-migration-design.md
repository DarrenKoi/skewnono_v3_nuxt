# Mock→Office Step-by-Step Migration — Design

Date: 2026-07-16
Status: Approved design, pending implementation plan

## 1. Goal

Make every feature under `back_dev_home/` independently switchable from mock
data to office data (OpenSearch/Redis) via one env var per feature, with a
contract test as the acceptance gate and a colocated English prompt file per
feature that the office LLM (GLM 5.2) can execute. The frontend never changes:
same URLs, same response shapes, no rebuild, no branching.

**Mixed operation is the standard scenario, not an edge case.** One Flask
process serves some features from office sources and the rest from mock for
weeks. The global default stays `mock`; completed features are flipped one at
a time with `SKEWNONO_<FEATURE>_PROVIDER=office`.

## 2. Current state

Provider-pattern adoption is partial. Inventory as of 2026-07-16:

| Feature | providers/ | contracts.py | contract test |
| ------- | ---------- | ------------ | ------------- |
| sem_list | yes | yes | no |
| msr_file | yes | no | mock-pinned only |
| meas_hist | yes | no | no |
| afm | yes | no | no |
| ebeam/hitachi/hardware | yes | yes | no |
| ebeam/hitachi/skew | yes | yes | no |
| ebeam/hitachi/storage | yes | yes | no |
| ebeam/hitachi/recipe_tat | yes | no | no |
| ebeam/hitachi/fail_issue | yes | no | no |
| activity | no | no | no |
| admin_logs | no | no | no |
| access_control | no | no | no |
| api_tokens | no | no | no |
| announcements | no | no | no |
| health | no | no | no |
| ebeam/cdsem/device_statistics | no | no | no |
| ebeam/hitachi/pm_planning | no | yes | no |
| ebeam/hitachi/recipe_search | no | no | no |
| ebeam/lateral_recipe | no | no | no |

Scope: restructure the 10 features without `providers/`, and backfill
`contracts.py` / contract tests / `MIGRATION.md` on the 9 that already have
the split. All 19 converge on one convention.

Out of scope:

- `_auth` — already swaps via its own `IdentityProvider` protocol
  (`LocalIdentityProvider` vs `CloudIdentityProvider`).
- Runtime response validation — rejected in favor of the pytest gate.
- Endpoint-level provider fallback — switching granularity is per feature.

## 3. Per-feature structure (the convention)

Every feature folder converges on the shape `sem_list` already has, plus the
prompt file:

```text
<feature>/
  __init__.py          # re-exports bp
  routes.py            # blueprint; imports ONLY from .data
  contracts.py         # TypedDicts for every response payload
  data.py              # thin switch: get_data_provider("<feature>") → provider
  MIGRATION.md         # colocated GLM 5.2 prompt (English)
  providers/
    __init__.py
    mock.py            # existing mock code, moved verbatim
    office.py          # NotImplementedError stubs + docstrings naming the
                       # office source (OpenSearch index / Redis key pattern)
  tests/
    __init__.py
    test_contract.py   # calls data.py functions, validates against contracts.py
```

Rules:

- `routes.py` imports only from `.data`. `data.py` lazy-imports the selected
  provider inside each function (existing `sem_list/data.py` pattern), so an
  incomplete `office.py` in the repo never executes until its env var is set.
- Feature env names follow the existing `get_data_provider()` convention:
  `activity` → `SKEWNONO_ACTIVITY_PROVIDER`. Nested ebeam features use bare
  keys, matching how the five existing hitachi features already register
  (`skew`, `storage`, `recipe_tat`, … → `recipe_search`, `device_statistics`).
- Mock code moves verbatim — this refactor changes zero behavior.

## 4. Shared contract validator

New module `back_dev_home/_core/contract_check.py` (~100 lines):
`assert_matches(value, ContractType)` structurally validates a value against a
TypedDict, recursing into `list[T]`, nested TypedDicts, `Literal`,
`Optional`/unions.

Policy:

- **Extra keys are allowed.** Office sources may return more fields; the
  frontend ignores them. Missing required keys or wrong types fail.
- Failure messages name the full path (`rows[3].eqp_id: expected str, got
  None`) so GLM can self-correct from pytest output alone.
- The validator ships with its own unit tests (`back_dev_home/_core/tests/`).

## 5. Contract tests — the provider-independent gate

Each `tests/test_contract.py` imports from **`data.py`, never
`providers.mock`**, so the active env var decides which provider is under
test:

- At home: `pytest back_dev_home` runs everything against mock; must stay
  green forever.
- At the office, the acceptance ritual per feature is:

```bash
SKEWNONO_ACTIVITY_PROVIDER=office pytest back_dev_home/activity
```

Green is the precondition for flipping the running server's env var. Beyond
shape checks, each test adds asserts for semantic invariants the TypedDict
cannot express (sort order, date format, empty-group inclusion) — sourced
from the "Notes" lines in `MIGRATION.md`.

The existing `msr_file/tests/test_contract.py` intentionally imports
`providers.mock` to pin mock-only invariants (forbidden office-gated keys).
It stays as-is; `msr_file` gains an additional provider-independent test.

## 6. MIGRATION.md — colocated GLM 5.2 prompt

One self-contained English file per feature, next to the code it describes.
Structure:

```markdown
# <feature> — office migration

## Rules (shared)
- Edit ONLY providers/office.py. Never touch routes.py / data.py /
  providers/mock.py / contracts.py.
- Normalize every result to the contracts.py shapes before returning.

## Endpoint: GET /api/<...>          ← one block per endpoint
- Handler: routes.py:<fn> → data.<fn>()
- Contract: <TypedDict name> (inlined source + one sample mock response)
- Mock behavior summary: <what the mock does, in 2-3 lines>
- Office data source: <!-- OFFICE: fill in index/key names on site -->
- Notes: <semantic expectations the frontend relies on — sort order,
  empty-value handling, date formats>

## Verify
SKEWNONO_<FEATURE>_PROVIDER=office pytest back_dev_home/<feature>
Definition of done: the command above is green.
```

The `<!-- OFFICE: ... -->` placeholders are filled at the office (index
names, Redis key patterns are not known/committable from home). Everything
else is written now so GLM needs no other context.

## 7. Central status doc

`docs/office-migration/STATUS.md`, in Korean (formal `~입니다` style, MD060
compact tables): one row per feature — endpoints, contract file, provider
status (mock/office), verified date. This is the office migration checklist;
it is the only central document, everything else is colocated.

## 8. Error handling

- Unknown provider value → existing `RuntimeError` from `get_data_provider`
  (kept as-is).
- Office stub called before implementation → `NotImplementedError` naming the
  exact env var to set back to `mock` (existing stub convention, kept).
- Contract violations are caught by the pytest gate before any flip; no
  runtime validation machinery.
- Env var changes require a Flask restart (process env is fixed at launch);
  a few seconds of downtime per flip is acceptable for an internal tool.

## 9. Refactor safety and testing

1. **Parity snapshot (temporary scaffolding).** Before moving any code,
   capture responses of every GET endpoint via Flask's test client; after the
   refactor the same requests must return identical JSON. Mocks with unseeded
   randomness (e.g. `activity`) get a fixed seed inside the snapshot harness
   only — normal runs are unchanged. The snapshot harness is deleted after
   the migration commits land; the contract tests remain.
2. **Full suite green.** Existing backend tests plus all new contract tests.
3. **Live check.** The running mock server (`/verify` flow) is exercised for
   at least two restructured features to confirm the frontend renders
   unchanged.

## 10. Ongoing enforcement — `home-to-office` project skill

The convention outlives this migration: new pages and endpoints will keep
being built at home. A project skill (`.claude/skills/home-to-office/`)
audits any feature — named explicitly or auto-detected from git changes —
against the convention before work is conveyed to the office: folder layout,
thin-switch `data.py`, routes-import discipline, endpoint↔MIGRATION.md
coverage, contract-test coverage, office-stub completeness, intact
`<!-- OFFICE: -->` placeholders, STATUS.md row, and both gate runs (mock
green; office switch raising `NotImplementedError` until implemented). It
auto-fixes mechanical gaps (missing stubs/tests/prompt blocks) but never
touches `providers/mock.py` logic or `routes.py`, and ends with a READY /
NOT READY verdict per feature.

## 11. Office workflow summary (per feature)

```text
1. GLM reads <feature>/MIGRATION.md, implements providers/office.py only
2. Fill <!-- OFFICE: --> placeholders (index/key names) as discovered
3. SKEWNONO_<FEATURE>_PROVIDER=office pytest back_dev_home/<feature>
4. Green → add env var to the Flask launch env, restart, update STATUS.md
5. Red or not ready → do nothing; mock keeps serving, frontend unaffected
```
