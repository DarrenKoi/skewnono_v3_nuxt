# Provider Presence Detection — Design

- **Date:** 2026-07-22
- **Scope:** `back_dev_home/_runtime/`, app factory, health blueprint
- **Status:** Approved design, pending implementation plan

## 1. Goal

Make the existence of `<feature>/providers/office.py` the single signal that a
feature is wired to office data. Adding pages must not add per-feature
bookkeeping in `.env` or in tracked Python.

## 2. Problem

The single fact *"this feature is wired to office"* is currently recorded three
times, on two machines, in two version-control states:

| Record | Lives where | Updated by |
| --- | --- | --- |
| `cp office_example.py office.py` | office machine, gitignored | office side |
| `SKEWNONO_<FEATURE>_PROVIDER=office` | office `.env`, gitignored | office side |
| `site.OFFICE_READY` | `_runtime/site.py`, **tracked** | home side, then push |

Three records means three chances to disagree, and the burden grows linearly
with feature count — 21 features today, 21 commented lines in `.env.example`.

The third record is the worst: promoting a feature requires a commit from the
*home* side asserting something only the *office* side can know. `OFFICE_READY`
is a cache, in git, of a fact that lives on another machine's filesystem. That
is why it goes stale.

Presence detection collapses all three into one: the `cp` that creates the
adapter is the same act that switches it on.

### 2.1 Prior art in this repo

Two existing mechanisms already do exactly this, and this design generalizes
them rather than introducing a new pattern:

- **Blueprint registration** (`back_dev_home/__init__.py:138`) discovers
  features by `rglob("routes.py")` — no tracked list of blueprints exists. It
  then *verifies* each hit exports a `Blueprint` and raises at boot if not
  (`__init__.py:144`). Glob to discover, assert to validate, fail at boot.
- **Hardware per-tab fallback** (`hardware/providers/office_example.py:44`,
  `_tab()`) already applies presence detection to hardware's seven tabs, and
  established the `exc.name` guard that separates "no adapter yet" from
  "adapter is broken".

## 3. Design

### 3.1 Resolution model

Two decisions that are currently tangled become independent:

- **mode** — a property of the machine: are we at the office?
- **readiness** — a property of the filesystem: is this feature wired?

Mode is a single derivation, evaluated per call rather than cached — env reads
are cheap, and tests monkeypatch these variables:

```python
def _mode() -> DataProvider:
    raw = os.environ.get("SKEWNONO_DATA_PROVIDER")
    if raw is not None:
        return _validated(raw)                       # explicit, either direction
    return "office" if detect_site() == "office" else "mock"
```

Then each feature resolves against it:

```python
def get_data_provider(feature: str) -> DataProvider:
    raw = os.environ.get(_feature_env_name(feature))
    if raw is not None:
        return _validated(raw, feature)              # per-feature override wins
    if _mode() == "office" and feature in OFFICE_READY:
        return "office"
    return "mock"
```

The full matrix:

| Feature env var | Mode | `office.py` present | Result |
| --- | --- | --- | --- |
| `=mock` | any | any | `mock` (escape hatch) |
| `=office` | any | yes | `office` |
| `=office` | any | no | **boot refusal** (§3.3) |
| unset | `office` | yes | `office` |
| unset | `office` | no | `mock`, logged |
| unset | `mock` | any | `mock` |

`get_data_provider()` keeps its exact current signature, so `chat/guard.py:68`,
`sharpness/office_example.py:133`, and the four contract-gate tests are
unaffected.

### 3.2 The registry

New module `back_dev_home/_runtime/office_registry.py`. Every feature's
directory name already equals the slug `get_data_provider()` receives — verified
across all 21 features — so the filesystem alone yields the mapping:

```text
sem_list/providers/office.py                       -> "sem_list"
ebeam/hitachi/hardware/providers/office.py         -> "hardware"
ebeam/cdsem/device_statistics/providers/office.py  -> "device_statistics"
```

```python
FEATURES     = _slugs("mock.py")      # {slug: Path} — every feature
OFFICE_READY = _slugs("office.py")    # {slug: Path} — those with an adapter
```

Both are mappings, not sets: `validate_env()` needs a feature's directory to
build the `cp` command in its error message (§3.3). Both are computed once at
import via `ROOT.glob("**/providers/<name>.py")`, with `_`-prefixed directories
skipped to mirror `__init__.py:140`.

**The glob pattern is load-bearing.** `**/providers/office.py` requires
`office.py` to sit *directly* inside a directory literally named `providers`,
so `hardware/providers/fdc/office.py` does **not** match — `fdc` is not
`providers`. This is the boundary between two layers of the same idea: the
global registry knows only about *features*; whether hardware's FDC tab
specifically is live stays hardware's private business inside `_tab()`. The
boundary is pinned by an explicit test (§5).

Three guards, all raising at import:

1. **Duplicate slug** — two directories with the same name both containing
   `providers/`. This collision is not new (`SKEWNONO_HARDWARE_PROVIDER`
   already assumes global slug uniqueness), but a glob would resolve it
   silently where an env var conflicts loudly. Raising converts a future
   silent-wrong-data bug into a boot crash.
2. **`OFFICE_READY ⊄ FEATURES`** — an `office.py` with no sibling `mock.py`,
   i.e. a stray adapter in a non-feature `providers/` directory.
3. Message text names the offending paths, not just the slug.

### 3.3 Boot validation and logging

`create_app()` calls `load_dotenv()` first (`__init__.py:117`), so validation
slots in immediately after, before blueprint registration — fail before doing
work.

`validate_env()` walks every `SKEWNONO_*_PROVIDER` variable set to `office`
(skipping the global `SKEWNONO_DATA_PROVIDER`, which selects mode, not a
feature) and raises when it cannot be honored, distinguishing two causes:

- slug not in `FEATURES` → unknown feature (catches typos such as
  `SKEWNONO_STORAGES_PROVIDER`)
- slug in `FEATURES` but not `OFFICE_READY` → raise with the literal fix:
  `cp back_dev_home/<path>/providers/office_example.py <path>/providers/office.py`

An explicit request for real fab data must never be silently answered with
fabricated numbers. This is the same principle as the `exc.name` guard, applied
to configuration rather than imports.

Then one INFO block: `site=<...> mode=<...>` followed by a line per feature
carrying provider **and reason** (`office.py found`, `no office.py`,
`forced by SKEWNONO_STORAGE_PROVIDER`, `mode=mock`).

### 3.4 `GET /api/health/providers`

Returns the same table as JSON:

```json
{
  "site": "office",
  "mode": "office",
  "features": [
    {"feature": "sem_list", "provider": "office", "reason": "office.py found"},
    {"feature": "skew", "provider": "mock", "reason": "no office.py"}
  ]
}
```

**This endpoint must not go through `health/data.py`'s own mock/office swap.**
It is runtime introspection, not phase-swappable data; a swappable version
could misreport itself in exactly the situation you would query it. It reads
`office_registry` directly from `health/routes.py`, alongside the existing
`/health/services` route.

Feature responses stay clean — no `mock ·` markers — consistent with the
decision already recorded in `hardware/providers/office_example.py:18`.

### 3.5 Semantic change to `SKEWNONO_DATA_PROVIDER`

`=office` currently means *"force every feature to office."* It will mean
*"office mode; presence decides per feature."* The old meaning was unusable in
practice — it 500s every unwired feature, which is precisely why `OFFICE_READY`
had to exist.

A useful consequence: `SKEWNONO_DATA_PROVIDER=mock` becomes a whole-instance
kill switch. One line returns the entire office app to a known-good state
without deleting any adapter.

`SKEWNONO_SITE=office` from home still works as an override, but now also
requires the relevant `office.py` to be present locally — mode alone no longer
implies readiness.

## 4. Files changed

| File | Change |
| --- | --- |
| `_runtime/office_registry.py` | **new** — globs, three guards, `resolve_all()`, `validate_env()` |
| `_runtime/data_provider.py` | two-step resolution; imports registry instead of `site.OFFICE_READY` |
| `_runtime/site.py` | delete `OFFICE_READY`; `detect_site()` unchanged |
| `__init__.py` | `validate_env()` + INFO block after `load_dotenv` |
| `health/routes.py` | add `GET /health/providers` |
| `.env.example` | 21 commented per-feature lines → short presence-detection explanation plus override examples |
| `docs/office-migration/STATUS.md` | note that it is now documentation only, mirrored nowhere in code |
| `<feature>/MIGRATION.md` | drop the "set the env var" step from each Verify section |
| `CLAUDE.md` | update the API Abstraction Layer section |

## 5. Testing

`_runtime/tests/test_site_provider.py` requires a rewrite, not additions: its
current assertions (office hostname → `sem_list == "office"`, line 45) become
false at home, where no `office.py` exists anywhere. Registry tests build fake
package trees under `tmp_path` with a monkeypatched root.

| Test | Asserts |
| --- | --- |
| resolution matrix | all six rows of §3.1 |
| escape hatch | `=mock` beats a present `office.py` |
| boot refusal | `=office` with no adapter raises, message contains the `cp` command |
| typo detection | `=office` for an unknown slug raises "unknown feature" |
| duplicate slug | two same-named feature dirs raise at import |
| orphan adapter | `office.py` without `mock.py` raises at import |
| layer boundary | `"fdc" not in OFFICE_READY` — per-tab adapters never enter the global registry |
| kill switch | `SKEWNONO_DATA_PROVIDER=mock` at office → every feature mock |
| home safety | home hostname → every feature mock even with adapters present |
| endpoint | `/api/health/providers` reports provider and reason per feature |

Contract-gate tests in the five features that call `get_data_provider()`
directly must keep passing untouched — that is the signature-compatibility
check.

## 6. Risks

**The `cp` is a commitment, not a preview.** Unwired features ship
`office_example.py` stubs that raise `NotImplementedError` (verified:
`announcements`, `activity`, `afm`, `skew`, `pm_planning`). Copying one to read
it would register that feature as office-ready and 500 the page. It fails
loudly rather than silently, so this is not a data-integrity hazard, but the
workflow rule becomes explicit: read the template in place; only `cp` when
implementing.

**A restart is required after `cp`.** The registry is computed once at import.
Flask's dev reloader handles this automatically; cloud deploys restart anyway.
Documented in `.env.example` and each `MIGRATION.md`.

**Mock served under an office banner is invisible in responses.** Mitigated by
§3.3 and §3.4, which are the reason both exist.

## 7. Out of scope

- Per-tab status in `/api/health/providers`. Hardware's `_tab()` logs its own
  fallbacks; special-casing one feature inside a generic endpoint would leak
  the layer boundary that §3.2 exists to protect.
- Hot reload of the registry without a restart.
- UI badges or `mock ·` markers in feature responses.
- The non-`providers/` swap surfaces: `chat`'s LLM configuration and
  `msr_file`'s FTP/MinIO handlers stay env-driven. Presence detection covers
  only the `providers/office.py` surface.

## 8. Payoff

Per-feature migration loses the step that crosses the home/office git boundary:

| Before | After |
| --- | --- |
| `cp office_example.py office.py` | `cp office_example.py office.py` |
| implement the adapter | implement the adapter |
| add `SKEWNONO_X_PROVIDER=office` to office `.env` | — |
| at home: add to `OFFICE_READY`, commit, push | — |
| — | restart |

The removed row is the one that does not scale with page count.
