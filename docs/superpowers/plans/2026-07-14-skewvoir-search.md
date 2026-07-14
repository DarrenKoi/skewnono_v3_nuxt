# Skewvoir 측정 결과 검색 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the stub skewvoir landing page (`측정 결과 검색`) into a working search screen — a search bar that finds measurements by tool / recipe / lot / date / msr, five real filter dropdowns, a results table, and a localStorage-backed "recently viewed" list.

**Architecture:** The query text is parsed **client-side** into structured fields (`app/utils/measHistQuery.ts`, a pure function). Those fields plus the filter dropdowns go to a new Flask endpoint `GET /api/meas-hist/search`, which filters the existing 600-row seeded mock in `meas_hist/data.py`. The 60-day retention window is enforced by the backend against a declared anchor date. A second endpoint `GET /api/meas-hist/facets` supplies dropdown options. Phase 2/3 swaps only the two `data.py` functions for OpenSearch queries.

**Tech Stack:** Nuxt 4 + NuxtUI 4 (`UPopover`, `UInput`, `UCheckbox`), Flask blueprints, `node --test` for the parser tests.

**Spec:** `docs/superpowers/specs/2026-07-14-skewvoir-search-design.md`

## Global Constraints

- **Retention anchor, not wall clock.** The mock's clock is frozen at `NOW = datetime(2026, 5, 10)` in `back_dev_home/meas_hist/data.py`. All 600 rows fall in `2026-03-11 → 2026-05-10`. Every date calculation — default range, presets, expiry — resolves against the backend-declared `anchor`, never `new Date()` / `today()`. Using wall clock yields zero rows.
- **Retention window is 60 days**, `RETENTION_DAYS = 60`.
- **OpenSearch result ceiling is `MAX_RESULT_WINDOW = 10000`.** `total` may exceed it; when it does, respond with `capped: true`.
- **Backend takes structured fields only.** No raw `q` parameter. Repeated params (`eq`, `fab`, `model`, `recipe`, `lot`, `msr`) are read with `request.args.getlist(...)`.
- **Same field OR, across fields AND.**
- **Blueprints auto-register.** `back_dev_home/__init__.py` does `rglob("routes.py")` — never add manual registration.
- **Page size** `DEFAULT_LIMIT = 50`. **Recently-viewed cap** is **15**.
- **Design tokens only** — `--sk-ink`, `--sk-ink-muted`, `--sk-ink-subtle`, `--sk-border`, `--sk-border-soft`, `--sk-surface`, `--sk-brand`, `--sk-brand-fg`, `--sk-chip-bg`, `--sk-chip-text`, `--sk-r-card`, `--sk-r-chip`, `--sk-r-nav`, `dashboard-surface`. Match the existing `SearchLanding.vue` idiom.
- **Run after frontend changes:** `npm --prefix front-dev-home run lint` and `npm --prefix front-dev-home test`.
- **Commit after every task.** Work directly on `main`.

## File Structure

**Create:**

| File | Responsibility |
| --- | --- |
| `front-dev-home/app/utils/measHistQuery.ts` | Pure parser: search text → `ParsedQuery`. Plus `removeToken`. |
| `front-dev-home/app/utils/measHistQuery.test.ts` | `node --test` tests for the parser. |
| `front-dev-home/app/composables/useMeasHistFacets.ts` | Cached facet fetch per tool type. |
| `front-dev-home/app/composables/useMeasHistSearch.ts` | Search state, request building, paging, client-side narrow. |
| `front-dev-home/app/composables/useSkewvoirRecentlyViewed.ts` | localStorage list, cap 15, expiry flag. |
| `front-dev-home/app/components/ebeam/skewvoir/search/SearchBar.vue` | Input, Search button, parsed-token chips. |
| `front-dev-home/app/components/ebeam/skewvoir/search/FilterBar.vue` | Five facet dropdowns + 초기화. |
| `front-dev-home/app/components/ebeam/skewvoir/search/FacetSelect.vue` | Reusable multi-select `UPopover` (with type-to-filter). |
| `front-dev-home/app/components/ebeam/skewvoir/search/ResultTable.vue` | Results, empty state, narrow box, 더 보기, 선택 분석. |
| `front-dev-home/app/components/ebeam/skewvoir/search/RecentlyViewed.vue` | Recently-viewed table with expired rows. |

**Modify:**

| File | Change |
| --- | --- |
| `back_dev_home/meas_hist/data.py` | Add `RETENTION_ANCHOR`, `RETENTION_DAYS`, `MAX_RESULT_WINDOW`, `search_meas_hist()`, `get_meas_hist_facets()`. |
| `back_dev_home/meas_hist/routes.py` | Add `/meas-hist/search` and `/meas-hist/facets`. |
| `front-dev-home/app/composables/useMeasHistApi.ts` | Add `searchMeasHist()`, `fetchMeasHistFacets()` + types. |
| `front-dev-home/app/components/ebeam/skewvoir/SearchLanding.vue` | Rewrite as orchestrator; delete placeholder panels and MP/3σ/outlier chips. |
| `front-dev-home/app/composables/useSkewvoirWorkspace.ts` | Delete `pinnedFilters` + `SkewvoirPinnedFilters`. |
| `front-dev-home/app/components/ebeam/skewvoir/workspace/LeftRail.vue` (and any other `pinnedFilters` consumer) | Drop the removed state. |
| `front-dev-home/app/pages/ebeam/{cd-sem,hv-sem}/skewvoir/analysis.vue` | Record the opened measurement into recently-viewed. |

---

## Task 1: Query parser (`measHistQuery.ts`)

Pure, no Vue, no network. This is the only real logic in the feature, so it is fully TDD'd.

**Files:**

- Create: `front-dev-home/app/utils/measHistQuery.ts`
- Test: `front-dev-home/app/utils/measHistQuery.test.ts`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `interface ParsedQuery { eq: string[], lot: string[], recipe: string[], msr: string[], date: string[], unknown: string[] }`
  - `interface KnownValues { eq: string[], recipe: string[] }`
  - `parseMeasHistQuery(text: string, known?: KnownValues): ParsedQuery`
  - `removeToken(text: string, token: string): string`
  - `PARSED_FIELDS: readonly ['eq', 'lot', 'recipe', 'msr', 'date', 'unknown']`

**Reference — real mock value shapes** (verified against `_all_rows()`):

| Field | Example |
| --- | --- |
| `eqp_id` | `ECXDX925`, `ECDX753`, `MCD018` (letters + 3 digits) |
| `lot_id` | `6LD257421`, `RKPB240012` (3–4 alnum + 6 digits) |
| `full_name` | `CNT/CNT_CONTACT_CHECK_ABC123_QUAL_00008` |
| `recipe_name` | `CNT_CONTACT_CHECK_ABC123_QUAL_00008` |
| `msr` | `20260315_CNT_CONTACT_CHECK_ABC123_QUAL_00008_6LD257421_ECXDX925` |

Note recipe names themselves contain underscores, so msr detection keys on the leading 8-digit date, not on a part count alone.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/measHistQuery.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseMeasHistQuery, removeToken } from './measHistQuery.ts'

const KNOWN = {
  eq: ['ECXDX925', 'ECDX753', 'MCD018'],
  recipe: ['CNT/CNT_CONTACT_CHECK_ABC123_QUAL_00008', 'ADI/ADI_CD_BIAS_001', 'DEF/DEF_REVIEW_001']
}

const EMPTY = { eq: [], lot: [], recipe: [], msr: [], date: [], unknown: [] }

test('empty input parses to all-empty', () => {
  assert.deepEqual(parseMeasHistQuery('', KNOWN), EMPTY)
  assert.deepEqual(parseMeasHistQuery('   ', KNOWN), EMPTY)
})

test('splits on whitespace, comma and semicolon alike', () => {
  const r = parseMeasHistQuery('ECXDX925, ECDX753; MCD018', KNOWN)
  assert.deepEqual(r.eq, ['ECXDX925', 'ECDX753', 'MCD018'])
})

test('tolerates repeated and trailing separators', () => {
  const r = parseMeasHistQuery('ECXDX925 ,,  ECDX753 ;', KNOWN)
  assert.deepEqual(r.eq, ['ECXDX925', 'ECDX753'])
  assert.deepEqual(r.unknown, [])
})

test('known equipment id is detected exactly, not by prefix guessing', () => {
  assert.deepEqual(parseMeasHistQuery('ECXDX925', KNOWN).eq, ['ECXDX925'])
  // Same prefix, not a real tool -> not an eq.
  assert.deepEqual(parseMeasHistQuery('ECXDX999', KNOWN).eq, [])
})

test('lot id shape is detected', () => {
  assert.deepEqual(parseMeasHistQuery('6LD257421', KNOWN).lot, ['6LD257421'])
  assert.deepEqual(parseMeasHistQuery('RKPB240012', KNOWN).lot, ['RKPB240012'])
})

test('msr is detected by its leading 8-digit date, despite underscores in the recipe', () => {
  const msr = '20260315_CNT_CONTACT_CHECK_ABC123_QUAL_00008_6LD257421_ECXDX925'
  const r = parseMeasHistQuery(msr, KNOWN)
  assert.deepEqual(r.msr, [msr])
  assert.deepEqual(r.date, [])
  assert.deepEqual(r.lot, [])
})

test('both date forms normalize to YYYY-MM-DD', () => {
  assert.deepEqual(parseMeasHistQuery('2026-05-10', KNOWN).date, ['2026-05-10'])
  assert.deepEqual(parseMeasHistQuery('20260510', KNOWN).date, ['2026-05-10'])
})

test('recipe matches full_name, bare recipe_name, and case-insensitive substring', () => {
  assert.deepEqual(parseMeasHistQuery('ADI/ADI_CD_BIAS_001', KNOWN).recipe, ['ADI/ADI_CD_BIAS_001'])
  assert.deepEqual(parseMeasHistQuery('ADI_CD_BIAS_001', KNOWN).recipe, ['ADI_CD_BIAS_001'])
  assert.deepEqual(parseMeasHistQuery('cd_bias', KNOWN).recipe, ['cd_bias'])
})

test('a token matching nothing is unknown', () => {
  const r = parseMeasHistQuery('zzz', KNOWN)
  assert.deepEqual(r.unknown, ['zzz'])
  assert.deepEqual(r.recipe, [])
})

test('field: prefix overrides shape rules', () => {
  // Looks like a lot, forced to recipe.
  assert.deepEqual(parseMeasHistQuery('recipe:6LD257421', KNOWN).recipe, ['6LD257421'])
  // Not a known eq, forced to eq.
  assert.deepEqual(parseMeasHistQuery('eq:ECXDX999', KNOWN).eq, ['ECXDX999'])
  assert.deepEqual(parseMeasHistQuery('lot:zzz', KNOWN).lot, ['zzz'])
  assert.deepEqual(parseMeasHistQuery('msr:abc', KNOWN).msr, ['abc'])
  assert.deepEqual(parseMeasHistQuery('date:20260510', KNOWN).date, ['2026-05-10'])
})

test('field: prefix is case-insensitive and empty values are ignored', () => {
  assert.deepEqual(parseMeasHistQuery('LOT:6LD257421', KNOWN).lot, ['6LD257421'])
  assert.deepEqual(parseMeasHistQuery('lot:', KNOWN), EMPTY)
})

test('same field accumulates, different fields coexist', () => {
  const r = parseMeasHistQuery('ECXDX925 MCD018 6LD257421 2026-05-10', KNOWN)
  assert.deepEqual(r.eq, ['ECXDX925', 'MCD018'])
  assert.deepEqual(r.lot, ['6LD257421'])
  assert.deepEqual(r.date, ['2026-05-10'])
})

test('duplicate tokens are de-duplicated', () => {
  assert.deepEqual(parseMeasHistQuery('MCD018 MCD018', KNOWN).eq, ['MCD018'])
})

test('without facets, shape rules still work and leftovers become recipe substrings', () => {
  const r = parseMeasHistQuery('ECXDX925 6LD257421 2026-05-10')
  assert.deepEqual(r.lot, ['6LD257421'])
  assert.deepEqual(r.date, ['2026-05-10'])
  // No known list to confirm against, so it stays a recipe guess rather than unknown.
  assert.deepEqual(r.recipe, ['ECXDX925'])
  assert.deepEqual(r.unknown, [])
})

test('removeToken drops only that token and leaves the rest usable', () => {
  assert.equal(removeToken('ECXDX925, MCD018 ; 6LD257421', 'MCD018'), 'ECXDX925 6LD257421')
  assert.equal(removeToken('lot:6LD257421 MCD018', '6LD257421'), 'MCD018')
  assert.equal(removeToken('MCD018', 'MCD018'), '')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `Cannot find module './measHistQuery.ts'`.

- [ ] **Step 3: Write the implementation**

Create `front-dev-home/app/utils/measHistQuery.ts`:

```ts
// Pure: turn the skewvoir search-bar text into structured query fields.
//
// The parser lives client-side (not in Flask) so the backend has a single
// structured input contract, and so detection can lean on the facets response
// — a token that *is* a known eqp_id needs no prefix regex to guess at.
// See docs/superpowers/specs/2026-07-14-skewvoir-search-design.md §4.

export interface ParsedQuery {
  eq: string[]
  lot: string[]
  recipe: string[]
  msr: string[]
  // Always normalized to YYYY-MM-DD.
  date: string[]
  // Tokens that matched no field — surfaced in the UI so a typo is
  // distinguishable from a genuine no-hit.
  unknown: string[]
}

// Real values from the facets endpoint. Optional: search must not block on
// facets loading, so the parser degrades to shape rules alone without them.
export interface KnownValues {
  eq: string[]
  recipe: string[]
}

export const PARSED_FIELDS = ['eq', 'lot', 'recipe', 'msr', 'date', 'unknown'] as const

type ParsedField = typeof PARSED_FIELDS[number]

const SEPARATORS = /[\s,;]+/
const PREFIXED = /^(lot|recipe|eq|msr|date):(.*)$/i
// 20260315_CNT_CONTACT_CHECK_..._6LD257421_ECXDX925 — recipe names contain
// underscores too, so the leading 8-digit date is what makes an msr an msr.
const MSR = /^\d{8}_.+_.+_.+$/
const DATE_DASHED = /^(\d{4})-(\d{2})-(\d{2})$/
const DATE_COMPACT = /^(\d{4})(\d{2})(\d{2})$/
// 6LD257421 (3 alnum + 6 digits), RKPB240012 (4 alnum + 6 digits).
const LOT = /^[A-Z0-9]{3,4}\d{6}$/i

const emptyQuery = (): ParsedQuery => ({ eq: [], lot: [], recipe: [], msr: [], date: [], unknown: [] })

// '20260510' | '2026-05-10' -> '2026-05-10'. null if neither.
const normalizeDate = (token: string): string | null => {
  const m = DATE_DASHED.exec(token) ?? DATE_COMPACT.exec(token)
  return m ? `${m[1]}-${m[2]}-${m[3]}` : null
}

// A recipe facet value is 'CNT/CNT_CONTACT_CHECK_001'. Users type either the
// full name, the bare recipe name, or a fragment of either.
const matchesKnownRecipe = (token: string, known: string[], exact: boolean): boolean => {
  const t = token.toLowerCase()
  return known.some((full) => {
    const f = full.toLowerCase()
    const bare = f.includes('/') ? f.slice(f.indexOf('/') + 1) : f
    return exact ? f === t || bare === t : f.includes(t)
  })
}

const classify = (token: string, known?: KnownValues): { field: ParsedField, value: string } => {
  const prefixed = PREFIXED.exec(token)
  if (prefixed) {
    const field = prefixed[1]!.toLowerCase() as 'lot' | 'recipe' | 'eq' | 'msr' | 'date'
    const raw = prefixed[2]!
    if (field === 'date') {
      const iso = normalizeDate(raw)
      return iso ? { field: 'date', value: iso } : { field: 'unknown', value: raw }
    }
    return { field, value: raw }
  }

  const iso = normalizeDate(token)
  if (iso) return { field: 'date', value: iso }

  if (MSR.test(token)) return { field: 'msr', value: token }

  if (known?.eq.includes(token)) return { field: 'eq', value: token }

  if (known && matchesKnownRecipe(token, known.recipe, true)) {
    return { field: 'recipe', value: token }
  }

  if (LOT.test(token)) return { field: 'lot', value: token }

  if (known) {
    return matchesKnownRecipe(token, known.recipe, false)
      ? { field: 'recipe', value: token }
      : { field: 'unknown', value: token }
  }

  // No facets yet — assume a recipe fragment rather than crying "unknown" at
  // something we simply cannot check.
  return { field: 'recipe', value: token }
}

export const parseMeasHistQuery = (text: string, known?: KnownValues): ParsedQuery => {
  const parsed = emptyQuery()
  const tokens = text.trim().split(SEPARATORS).filter(Boolean)

  for (const token of tokens) {
    const { field, value } = classify(token, known)
    if (!value) continue
    const bucket = parsed[field]
    if (!bucket.includes(value)) bucket.push(value)
  }

  return parsed
}

// Drop one token from the raw text (used by the × on a parsed chip). Matches
// the bare token and any `field:token` form, and re-joins on single spaces so
// the remaining text stays well-formed.
export const removeToken = (text: string, token: string): string =>
  text
    .trim()
    .split(SEPARATORS)
    .filter(Boolean)
    .filter((raw) => {
      const prefixed = PREFIXED.exec(raw)
      const bare = prefixed ? prefixed[2]! : raw
      return bare.toLowerCase() !== token.toLowerCase()
    })
    .join(' ')
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm --prefix front-dev-home test`
Expected: PASS — all `measHistQuery` tests green, and the pre-existing 19 test files still green.

- [ ] **Step 5: Lint**

Run: `npm --prefix front-dev-home run lint`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/measHistQuery.ts front-dev-home/app/utils/measHistQuery.test.ts
git commit -m "feat(skewvoir): search-text parser for measurement search"
```

---

## Task 2: Backend search + facets

**Files:**

- Modify: `back_dev_home/meas_hist/data.py`
- Modify: `back_dev_home/meas_hist/routes.py`

**Interfaces:**

- Consumes: existing `_all_rows()`, `MeasHistRow`, `ToolType`, `NOW`, `HISTORY_DAYS` in `data.py`.
- Produces:
  - `RETENTION_ANCHOR: datetime`, `RETENTION_DAYS = 60`, `MAX_RESULT_WINDOW = 10000`, `DEFAULT_LIMIT = 50`
  - `search_meas_hist(tool_type, fab, model, eq, recipe, lot, msr, date_from, date_to, offset, limit) -> MeasHistSearchResponse`
  - `get_meas_hist_facets(tool_type) -> MeasHistFacetsResponse`
  - Endpoints `GET /api/meas-hist/search`, `GET /api/meas-hist/facets`

- [ ] **Step 1: Add the search + facets data layer**

Append to `back_dev_home/meas_hist/data.py` (and extend `__all__`):

```python
__all__ = [
    "MeasHistRow",
    "MeasHistResponse",
    "MeasHistSearchResponse",
    "MeasHistFacetsResponse",
    "ToolType",
    "get_meas_hist",
    "find_meas_hist_by_msr",
    "search_meas_hist",
    "get_meas_hist_facets",
    "RETENTION_DAYS",
    "MAX_RESULT_WINDOW",
    "DEFAULT_LIMIT",
]
```

```python
# --- Search -----------------------------------------------------------------
#
# Phase 1 filters the seeded rows in memory. Phase 2/3 replaces the bodies of
# search_meas_hist / get_meas_hist_facets with OpenSearch queries (a
# bool{must:[terms...]} + a terms aggregation). Routes and frontend do not change.

RETENTION_DAYS = 60
# OpenSearch index.max_result_window default. A retrieval ceiling, not a promise
# to the browser: `total` may exceed it, in which case `capped` is True.
MAX_RESULT_WINDOW = 10000
DEFAULT_LIMIT = 50

# The clock the retention window is measured from. Phase 1 pins it to the mock's
# frozen NOW so the 60-day window actually contains the seeded rows; Phase 2/3
# swaps this one line for datetime.now(timezone.utc).
RETENTION_ANCHOR = NOW


class MeasHistRange(TypedDict):
    from_: str
    to: str
    anchor: str


class MeasHistSearchResponse(TypedDict):
    total: int
    capped: bool
    offset: int
    limit: int
    range: dict[str, str]
    out_of_retention: bool
    rows: list[MeasHistRow]


class MeasHistFacetValue(TypedDict):
    value: str
    count: int


class MeasHistFacetsResponse(TypedDict):
    tool_type: ToolType | None
    anchor: str
    retention_days: int
    fab: list[MeasHistFacetValue]
    model: list[MeasHistFacetValue]
    eq: list[MeasHistFacetValue]
    recipe: list[MeasHistFacetValue]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _retention_window() -> tuple[datetime, datetime]:
    end = RETENTION_ANCHOR
    return end - timedelta(days=RETENTION_DAYS), end


def _resolve_window(
    date_from: str | None,
    date_to: str | None
) -> tuple[datetime, datetime, bool]:
    """Intersect the caller's range with the retention window.

    The window is a guarantee, not a default: a stale bookmark or a hand-edited
    URL must never widen the scan past retention. Returns (start, end,
    out_of_retention) — the flag says the caller's range fell entirely outside.
    """
    floor, ceiling = _retention_window()

    requested_start = _parse_date(date_from)
    requested_end = _parse_date(date_to)

    if requested_start and requested_start > ceiling:
        return floor, ceiling, True
    if requested_end and requested_end < floor:
        return floor, ceiling, True

    start = max(requested_start, floor) if requested_start else floor
    # `to` is inclusive of the whole day.
    end = min(requested_end + timedelta(days=1), ceiling) if requested_end else ceiling

    if start > end:
        return floor, ceiling, True

    return start, end, False


def _row_time(row: MeasHistRow) -> datetime:
    return datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))


def _matches_recipe_term(row: MeasHistRow, term: str) -> bool:
    """Recipe terms are substrings — the search bar accepts fragments."""
    needle = term.lower()
    return needle in row["full_name"].lower() or needle in row["recipe_name"].lower()


def search_meas_hist(
    tool_type: ToolType | None = None,
    fab: list[str] | None = None,
    model: list[str] | None = None,
    eq: list[str] | None = None,
    recipe: list[str] | None = None,
    lot: list[str] | None = None,
    msr: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT
) -> MeasHistSearchResponse:
    start, end, out_of_retention = _resolve_window(date_from, date_to)

    fab_set = {v.upper() for v in (fab or [])}
    model_set = {v.upper() for v in (model or [])}
    eq_set = {v.upper() for v in (eq or [])}
    lot_set = {v.upper() for v in (lot or [])}
    msr_set = set(msr or [])
    recipe_terms = [v for v in (recipe or []) if v]

    rows: list[MeasHistRow] = []
    if not out_of_retention:
        for row in _all_rows():
            if tool_type and row["tool_type"] != tool_type:
                continue

            ts = _row_time(row)
            if ts < start or ts > end:
                continue

            # Values within a field OR together; fields AND together.
            if fab_set and row["fab_name"].upper() not in fab_set:
                continue
            if model_set and row["eqp_model_cd"].upper() not in model_set:
                continue
            if eq_set and row["eqp_id"].upper() not in eq_set:
                continue
            if lot_set and row["lot_id"].upper() not in lot_set:
                continue
            if msr_set and row["msr"] not in msr_set:
                continue
            if recipe_terms and not any(_matches_recipe_term(row, t) for t in recipe_terms):
                continue

            rows.append(row)

    rows.sort(key=lambda r: r["timestamp"], reverse=True)

    total = len(rows)
    capped = total > MAX_RESULT_WINDOW
    retrievable = rows[:MAX_RESULT_WINDOW]

    offset = max(offset, 0)
    limit = max(1, min(limit, DEFAULT_LIMIT * 10))
    page = retrievable[offset:offset + limit]

    return MeasHistSearchResponse(
        total=total,
        capped=capped,
        offset=offset,
        limit=limit,
        range={
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
            "anchor": RETENTION_ANCHOR.strftime("%Y-%m-%d")
        },
        out_of_retention=out_of_retention,
        rows=page
    )


def _facet_counts(rows: tuple[MeasHistRow, ...], key: str) -> list[MeasHistFacetValue]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[key]] = counts.get(row[key], 0) + 1
    return [
        MeasHistFacetValue(value=value, count=count)
        for value, count in sorted(counts.items())
    ]


def get_meas_hist_facets(tool_type: ToolType | None = None) -> MeasHistFacetsResponse:
    """Dropdown options — only values that actually exist inside retention.

    Phase 2/3: a terms aggregation over the same bool filter.
    """
    start, end = _retention_window()

    rows = tuple(
        row for row in _all_rows()
        if (not tool_type or row["tool_type"] == tool_type)
        and start <= _row_time(row) <= end
    )

    return MeasHistFacetsResponse(
        tool_type=tool_type,
        anchor=RETENTION_ANCHOR.strftime("%Y-%m-%d"),
        retention_days=RETENTION_DAYS,
        fab=_facet_counts(rows, "fab_name"),
        model=_facet_counts(rows, "eqp_model_cd"),
        eq=_facet_counts(rows, "eqp_id"),
        recipe=_facet_counts(rows, "full_name")
    )
```

Note `MeasHistRange` is declared but the response builds `range` as a plain dict — `from` is a Python keyword and cannot be a TypedDict field via class syntax. Delete the `MeasHistRange` class if the linter flags it as unused; the plain dict is the shipped shape.

- [ ] **Step 2: Add the routes**

Replace `back_dev_home/meas_hist/routes.py` with:

```python
from flask import Blueprint, jsonify, request

from back_dev_home.meas_hist.data import (
    DEFAULT_LIMIT,
    ToolType,
    get_meas_hist,
    get_meas_hist_facets,
    search_meas_hist,
)


bp = Blueprint("meas_hist", __name__)

VALID_TOOL_TYPES: tuple[ToolType, ...] = ("cd-sem", "hv-sem")


def _resolve_tool_type() -> ToolType | None:
    raw = (request.args.get("tool_type") or "").strip().lower()
    return raw if raw in VALID_TOOL_TYPES else None


def _resolve_fab_name() -> str | None:
    raw = (request.args.get("fab_name") or "").strip().upper()
    return raw or None


def _resolve_recipe_name() -> str | None:
    raw = (request.args.get("recipe_name") or "").strip()
    return raw or None


def _list_arg(name: str) -> list[str]:
    """Repeated query params (?eq=A&eq=B) — values within a field OR together."""
    return [value.strip() for value in request.args.getlist(name) if value.strip()]


def _int_arg(name: str, default: int) -> int:
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


@bp.get("/meas-hist")
def meas_hist_index():
    return jsonify(get_meas_hist(
        tool_type=_resolve_tool_type(),
        fab_name=_resolve_fab_name(),
        recipe_name=_resolve_recipe_name()
    ))


@bp.get("/meas-hist/search")
def meas_hist_search():
    return jsonify(search_meas_hist(
        tool_type=_resolve_tool_type(),
        fab=_list_arg("fab"),
        model=_list_arg("model"),
        eq=_list_arg("eq"),
        recipe=_list_arg("recipe"),
        lot=_list_arg("lot"),
        msr=_list_arg("msr"),
        date_from=request.args.get("from"),
        date_to=request.args.get("to"),
        offset=_int_arg("offset", 0),
        limit=_int_arg("limit", DEFAULT_LIMIT)
    ))


@bp.get("/meas-hist/facets")
def meas_hist_facets():
    return jsonify(get_meas_hist_facets(tool_type=_resolve_tool_type()))
```

- [ ] **Step 3: Verify against the running backend**

Start Flask if it is not already up:

```bash
.venv/bin/python -m flask --app index run --port 5000
```

In another shell, verify each guarantee. Expected results are stated — if one does not hold, the implementation is wrong, not the expectation.

```bash
# Facets: anchor is the mock's frozen clock, not today.
curl -s 'http://localhost:5000/api/meas-hist/facets?tool_type=cd-sem' | python3 -c "import json,sys; d=json.load(sys.stdin); print('anchor', d['anchor'], 'retention', d['retention_days'], 'fabs', len(d['fab']), 'eqs', len(d['eq']), 'recipes', len(d['recipe']))"
# Expect: anchor 2026-05-10 retention 60 ... non-zero counts

# Default window returns rows (this is the check that catches wall-clock bugs).
curl -s 'http://localhost:5000/api/meas-hist/search?tool_type=cd-sem' | python3 -c "import json,sys; d=json.load(sys.stdin); print('total', d['total'], 'rows', len(d['rows']), 'range', d['range'], 'capped', d['capped'])"
# Expect: total > 0, rows <= 50, range.from 2026-03-11, range.to 2026-05-10, capped False

# A range fully outside retention: zero rows, flagged.
curl -s 'http://localhost:5000/api/meas-hist/search?tool_type=cd-sem&from=2020-01-01&to=2020-02-01' | python3 -c "import json,sys; d=json.load(sys.stdin); print('total', d['total'], 'out_of_retention', d['out_of_retention'])"
# Expect: total 0 out_of_retention True

# A caller trying to widen past retention gets clamped, not obeyed.
curl -s 'http://localhost:5000/api/meas-hist/search?tool_type=cd-sem&from=2000-01-01&to=2030-01-01' | python3 -c "import json,sys; d=json.load(sys.stdin); print('range', d['range'])"
# Expect: range.from 2026-03-11, range.to 2026-05-10

# Same field ORs, different fields AND. Pick two real eq ids from the facets call.
curl -s 'http://localhost:5000/api/meas-hist/search?tool_type=cd-sem&eq=ECXDX925&eq=ECDX753' | python3 -c "import json,sys; d=json.load(sys.stdin); print('eqs', sorted({r['eqp_id'] for r in d['rows']}))"
# Expect: only those two ids appear

# Paging.
curl -s 'http://localhost:5000/api/meas-hist/search?tool_type=cd-sem&offset=50&limit=50' | python3 -c "import json,sys; d=json.load(sys.stdin); print('offset', d['offset'], 'rows', len(d['rows']))"
```

- [ ] **Step 4: Commit**

```bash
git add back_dev_home/meas_hist/data.py back_dev_home/meas_hist/routes.py
git commit -m "feat(meas-hist): search + facets endpoints with 60d retention clamp"
```

---

## Task 3: API composable + facets composable

**Files:**

- Modify: `front-dev-home/app/composables/useMeasHistApi.ts`
- Create: `front-dev-home/app/composables/useMeasHistFacets.ts`

**Interfaces:**

- Consumes: `joinApiPath` from `~/utils/apiPath`; the Task 2 endpoints.
- Produces:
  - `interface MeasHistFacetValue { value: string, count: number }`
  - `interface MeasHistFacets { tool_type, anchor: string, retention_days: number, fab, model, eq, recipe: MeasHistFacetValue[] }`
  - `interface MeasHistSearchParams { toolType, fab?, model?, eq?, recipe?, lot?, msr?: string[], from?, to?: string, offset?, limit?: number }`
  - `interface MeasHistSearchResponse { total, offset, limit: number, capped: boolean, out_of_retention: boolean, range: { from: string, to: string, anchor: string }, rows: MeasHistRow[] }`
  - `searchMeasHist(params)`, `fetchMeasHistFacets(toolType)` on `useMeasHistApi()`
  - `useMeasHistFacets(toolType)` → `{ facets, pending, error, known }` where `known: ComputedRef<KnownValues>`

- [ ] **Step 1: Extend `useMeasHistApi.ts`**

Append to the existing file (keep `fetchMeasHist` and the existing types untouched — the 측정 이력 view still uses them):

```ts
export interface MeasHistFacetValue {
  value: string
  count: number
}

export interface MeasHistFacets {
  tool_type: MeasHistToolType | null
  // The clock the retention window is measured from. Phase 1 pins this to the
  // mock's frozen NOW; never substitute wall-clock today.
  anchor: string
  retention_days: number
  fab: MeasHistFacetValue[]
  model: MeasHistFacetValue[]
  eq: MeasHistFacetValue[]
  recipe: MeasHistFacetValue[]
}

export interface MeasHistSearchParams {
  toolType: MeasHistToolType
  fab?: string[]
  model?: string[]
  eq?: string[]
  recipe?: string[]
  lot?: string[]
  msr?: string[]
  from?: string
  to?: string
  offset?: number
  limit?: number
}

export interface MeasHistSearchResponse {
  total: number
  capped: boolean
  offset: number
  limit: number
  range: { from: string, to: string, anchor: string }
  out_of_retention: boolean
  rows: MeasHistRow[]
}
```

Inside `useMeasHistApi()`, before the `return`:

```ts
  const searchMeasHist = async (params: MeasHistSearchParams): Promise<MeasHistSearchResponse> => {
    // Repeated params (?eq=A&eq=B) are how a field ORs its values.
    const query: Record<string, string | string[] | number> = { tool_type: params.toolType }

    for (const key of ['fab', 'model', 'eq', 'recipe', 'lot', 'msr'] as const) {
      const values = params[key]
      if (values?.length) query[key] = values
    }
    if (params.from) query.from = params.from
    if (params.to) query.to = params.to
    if (params.offset) query.offset = params.offset
    if (params.limit) query.limit = params.limit

    return await $fetch<MeasHistSearchResponse>(joinApiPath(base, '/meas-hist/search'), { query })
  }

  const fetchMeasHistFacets = async (toolType: MeasHistToolType): Promise<MeasHistFacets> =>
    await $fetch<MeasHistFacets>(joinApiPath(base, '/meas-hist/facets'), {
      query: { tool_type: toolType }
    })
```

And extend the return: `return { fetchMeasHist, searchMeasHist, fetchMeasHistFacets }`.

- [ ] **Step 2: Create `useMeasHistFacets.ts`**

```ts
import type { MeasHistFacets, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { KnownValues } from '~/utils/measHistQuery'

// Facet options for the search filters. One shared useAsyncData cache key per
// tool type, so every dropdown and the query parser read the same fetch.
export const useMeasHistFacets = (toolType: MeasHistToolType) => {
  const { fetchMeasHistFacets } = useMeasHistApi()

  const { data: facets, pending, error } = useAsyncData<MeasHistFacets>(
    `meas-hist-facets:${toolType}`,
    () => fetchMeasHistFacets(toolType),
    {
      default: () => ({
        tool_type: toolType,
        anchor: '',
        retention_days: 60,
        fab: [],
        model: [],
        eq: [],
        recipe: []
      }),
      getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
    }
  )

  // What the search-text parser needs to identify a token by exact match
  // rather than by guessing at its shape.
  const known = computed<KnownValues>(() => ({
    eq: (facets.value?.eq ?? []).map(v => v.value),
    recipe: (facets.value?.recipe ?? []).map(v => v.value)
  }))

  // Empty until facets land; callers must not compute dates from wall clock.
  const anchor = computed(() => facets.value?.anchor ?? '')
  const retentionDays = computed(() => facets.value?.retention_days ?? 60)

  return { facets, pending, error, known, anchor, retentionDays }
}
```

- [ ] **Step 3: Typecheck and lint**

Run: `npm --prefix front-dev-home run lint`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/composables/useMeasHistApi.ts front-dev-home/app/composables/useMeasHistFacets.ts
git commit -m "feat(skewvoir): meas-hist search + facets client"
```

---

## Task 4: Search state composable

**Files:**

- Create: `front-dev-home/app/composables/useMeasHistSearch.ts`

**Interfaces:**

- Consumes: `useMeasHistApi().searchMeasHist`, `useMeasHistFacets`, `parseMeasHistQuery` from `~/utils/measHistQuery`.
- Produces: `useMeasHistSearch(toolType)` →
  `{ queryText, filters, parsed, rows, narrowedRows, narrowText, total, capped, outOfRetention, loaded, pending, error, hasMore, searched, search, loadMore, reset, resetFilters, hasActiveFilters, defaultRange, anchor, facets, facetsPending }`

- [ ] **Step 1: Create the composable**

```ts
import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import { parseMeasHistQuery } from '~/utils/measHistQuery'

export interface MeasHistFilters {
  fab: string[]
  model: string[]
  eq: string[]
  recipe: string[]
  from: string
  to: string
}

const PAGE_SIZE = 50

// Subtract days from an ISO YYYY-MM-DD without touching wall clock.
const shiftIso = (iso: string, days: number): string => {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1))
  dt.setUTCDate(dt.getUTCDate() - days)
  return dt.toISOString().slice(0, 10)
}

export const useMeasHistSearch = (toolType: MeasHistToolType) => {
  const { searchMeasHist } = useMeasHistApi()
  const { facets, pending: facetsPending, known, anchor, retentionDays } = useMeasHistFacets(toolType)

  const queryText = ref('')
  const narrowText = ref('')

  // The retention window is anchored to the backend's declared clock, never to
  // wall-clock today — the Phase 1 mock's data ends at a frozen NOW.
  const defaultRange = computed(() => ({
    start: anchor.value ? shiftIso(anchor.value, retentionDays.value) : '',
    end: anchor.value
  }))

  const filters = ref<MeasHistFilters>({ fab: [], model: [], eq: [], recipe: [], from: '', to: '' })

  // Chips render as you type — no round-trip needed to see how a token was read.
  const parsed = computed(() => parseMeasHistQuery(queryText.value, known.value))

  const rows = ref<MeasHistRow[]>([])
  const total = ref(0)
  const capped = ref(false)
  const outOfRetention = ref(false)
  const pending = ref(false)
  const error = ref<string | null>(null)
  // False until the first search runs — drives the "type something" empty state.
  const searched = ref(false)

  const hasActiveFilters = computed(() =>
    filters.value.fab.length > 0
    || filters.value.model.length > 0
    || filters.value.eq.length > 0
    || filters.value.recipe.length > 0
    || Boolean(filters.value.from)
    || Boolean(filters.value.to)
  )

  const hasMore = computed(() => rows.value.length < Math.min(total.value, 10000))

  // Search-bar fields and dropdown fields feed the same request params.
  const union = (a: string[], b: string[]) => [...new Set([...a, ...b])]

  const buildParams = (offset: number) => {
    const p = parsed.value
    const dates = [...p.date].sort()
    const from = filters.value.from || dates[0] || defaultRange.value.start
    const to = filters.value.to || dates[dates.length - 1] || defaultRange.value.end

    return {
      toolType,
      fab: filters.value.fab,
      model: filters.value.model,
      eq: union(filters.value.eq, p.eq),
      recipe: union(filters.value.recipe, p.recipe),
      lot: p.lot,
      msr: p.msr,
      from,
      to,
      offset,
      limit: PAGE_SIZE
    }
  }

  const run = async (offset: number) => {
    pending.value = true
    error.value = null
    try {
      const res = await searchMeasHist(buildParams(offset))
      rows.value = offset === 0 ? res.rows : [...rows.value, ...res.rows]
      total.value = res.total
      capped.value = res.capped
      outOfRetention.value = res.out_of_retention
    } catch {
      // Keep the current rows on failure — losing results to a transient blip
      // is worse than showing stale ones next to a retry.
      error.value = '검색에 실패했습니다.'
    } finally {
      pending.value = false
    }
  }

  // Explicit: Enter or the Search button. Searching per keystroke would fire a
  // full OpenSearch query for every character of a lot id.
  const search = async () => {
    searched.value = true
    narrowText.value = ''
    await run(0)
  }

  const loadMore = async () => {
    if (!hasMore.value || pending.value) return
    await run(rows.value.length)
  }

  // Instant, local narrowing of the rows already loaded. Never hits the network.
  const narrowedRows = computed(() => {
    const needle = narrowText.value.trim().toLowerCase()
    if (!needle) return rows.value
    return rows.value.filter(row =>
      row.lot_id.toLowerCase().includes(needle)
      || row.full_name.toLowerCase().includes(needle)
      || row.eqp_id.toLowerCase().includes(needle)
      || row.fab_name.toLowerCase().includes(needle)
    )
  })

  const resetFilters = () => {
    filters.value = { fab: [], model: [], eq: [], recipe: [], from: '', to: '' }
  }

  const reset = () => {
    queryText.value = ''
    narrowText.value = ''
    resetFilters()
    rows.value = []
    total.value = 0
    capped.value = false
    outOfRetention.value = false
    error.value = null
    searched.value = false
  }

  // A dropdown change is one deliberate act, so it re-searches immediately —
  // unlike typing, which waits for Enter.
  watch(() => filters.value, () => {
    if (searched.value) void search()
  }, { deep: true })

  return {
    queryText,
    narrowText,
    filters,
    parsed,
    rows,
    narrowedRows,
    total,
    capped,
    outOfRetention,
    pending,
    error,
    searched,
    hasMore,
    hasActiveFilters,
    defaultRange,
    anchor,
    retentionDays,
    facets,
    facetsPending,
    search,
    loadMore,
    reset,
    resetFilters
  }
}
```

- [ ] **Step 2: Lint**

Run: `npm --prefix front-dev-home run lint`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/composables/useMeasHistSearch.ts
git commit -m "feat(skewvoir): search state composable"
```

---

## Task 5: Recently-viewed composable

**Files:**

- Create: `front-dev-home/app/composables/useSkewvoirRecentlyViewed.ts`

**Interfaces:**

- Consumes: `MeasHistToolType`.
- Produces:
  - `interface SkewvoirRecentItem { msr: string, toolType: MeasHistToolType, lot: string, recipe: string, eq: string, fab: string, capturedAt: string, viewedAt: string }`
  - `interface SkewvoirRecentEntry extends SkewvoirRecentItem { expired: boolean }`
  - `useSkewvoirRecentlyViewed(toolType)` → `{ items, record, remove, clear, refresh }` where `record(item: SkewvoirRecentItem, anchor: string)` and `items` is a `ComputedRef<SkewvoirRecentEntry[]>` — call `setAnchor(anchor)` to enable expiry.

Mirror `useSkewvoirSavedViews.ts` exactly: module-level `readAll`/`writeAll`, `useState` for cross-component reactivity, `import.meta.client` guards. Phase 2/3 swaps the storage internals for a Flask blueprint without changing this surface.

- [ ] **Step 1: Create the composable**

```ts
import type { MeasHistToolType } from '~/composables/useMeasHistApi'

// A measurement the user opened in the analysis workspace. Phase 1 persists to
// localStorage (fully offline), same as useSkewvoirSavedViews. Phase 2/3 swaps
// the read/write internals for a per-user Flask blueprint; this surface stays.
export interface SkewvoirRecentItem {
  msr: string
  toolType: MeasHistToolType
  lot: string
  recipe: string
  eq: string
  fab: string
  capturedAt: string
  viewedAt: string
}

export interface SkewvoirRecentEntry extends SkewvoirRecentItem {
  // Outside the 60-day retention window: the row is remembered but the data is
  // gone, so the entry is shown greyed rather than silently dropped.
  expired: boolean
}

const STORAGE_KEY = 'skewvoir-recently-viewed'
const MAX_ITEMS = 15
const RETENTION_DAYS = 60

const readAll = (): SkewvoirRecentItem[] => {
  if (!import.meta.client) return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? (parsed as SkewvoirRecentItem[]) : []
  } catch {
    return []
  }
}

const writeAll = (items: SkewvoirRecentItem[]) => {
  if (!import.meta.client) return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
}

const shiftIso = (iso: string, days: number): string => {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1))
  dt.setUTCDate(dt.getUTCDate() - days)
  return dt.toISOString().slice(0, 10)
}

export const useSkewvoirRecentlyViewed = (toolType: MeasHistToolType) => {
  const all = useState<SkewvoirRecentItem[]>('skewvoir-recently-viewed-store', () => readAll())
  // The retention floor comes from the backend's anchor, never wall clock —
  // the Phase 1 mock's clock is frozen well before today.
  const anchor = useState<string>('skewvoir-recent-anchor', () => '')

  const setAnchor = (value: string) => {
    if (value) anchor.value = value
  }

  const items = computed<SkewvoirRecentEntry[]>(() => {
    const floor = anchor.value ? shiftIso(anchor.value, RETENTION_DAYS) : ''
    return all.value
      .filter(item => item.toolType === toolType)
      .map(item => ({
        ...item,
        expired: Boolean(floor) && item.capturedAt.slice(0, 10) < floor
      }))
  })

  const record = (item: SkewvoirRecentItem) => {
    const deduped = all.value.filter(existing => existing.msr !== item.msr)
    all.value = [item, ...deduped].slice(0, MAX_ITEMS)
    writeAll(all.value)
  }

  const remove = (msr: string) => {
    all.value = all.value.filter(item => item.msr !== msr)
    writeAll(all.value)
  }

  const clear = () => {
    all.value = all.value.filter(item => item.toolType !== toolType)
    writeAll(all.value)
  }

  const refresh = () => {
    all.value = readAll()
  }

  return { items, record, remove, clear, refresh, setAnchor }
}
```

Note the cap is applied across **all** tool types (a single 15-item list), matching how `useSkewvoirSavedViews` keeps one store and filters on read.

- [ ] **Step 2: Lint**

Run: `npm --prefix front-dev-home run lint`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/composables/useSkewvoirRecentlyViewed.ts
git commit -m "feat(skewvoir): recently-viewed measurements in localStorage"
```

---

## Task 6: Search bar + filter bar components

**Files:**

- Create: `front-dev-home/app/components/ebeam/skewvoir/search/FacetSelect.vue`
- Create: `front-dev-home/app/components/ebeam/skewvoir/search/SearchBar.vue`
- Create: `front-dev-home/app/components/ebeam/skewvoir/search/FilterBar.vue`

Auto-import names are `EbeamSkewvoirSearchFacetSelect`, `EbeamSkewvoirSearchSearchBar`, `EbeamSkewvoirSearchFilterBar`.

**Interfaces:**

- Consumes: `MeasHistFacetValue`, `MeasHistFilters`, `ParsedQuery`, `removeToken`, existing `EbeamDateRangePopover`.
- Produces:
  - `FacetSelect` props `{ label: string, options: MeasHistFacetValue[], modelValue: string[], searchable?: boolean, disabled?: boolean }`, emits `update:modelValue`
  - `SearchBar` props `{ modelValue: string, parsed: ParsedQuery, pending?: boolean }`, emits `update:modelValue`, `search`
  - `FilterBar` props `{ filters: MeasHistFilters, facets: MeasHistFacets, disabled?: boolean, anchor: string, retentionDays: number }`, emits `update:filters`, `reset`

- [ ] **Step 1: `FacetSelect.vue` — the dropdown that was missing**

The current filter row renders bare `<button>` elements with a chevron and no popover, which is why nothing opens. This is a real `UPopover` multi-select.

```vue
<template>
  <UPopover :content="{ align: 'start' }">
    <button
      type="button"
      :disabled="disabled"
      class="inline-flex h-7 items-center gap-1.5 rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-surface) px-2.5 text-[12px] text-zinc-600 hover:bg-zinc-500/5 disabled:cursor-not-allowed disabled:opacity-50 dark:text-zinc-300"
      :class="{ 'border-(--sk-brand)': modelValue.length > 0 }"
    >
      <span class="text-(--sk-ink-muted)">{{ label }}:</span>
      <span class="font-medium text-zinc-800 dark:text-zinc-100">
        {{ summary }}
      </span>
      <UIcon
        name="i-lucide-chevron-down"
        class="h-3 w-3 opacity-50"
      />
    </button>

    <template #content>
      <div class="w-64 p-2">
        <UInput
          v-if="searchable"
          v-model="filterText"
          size="xs"
          icon="i-lucide-search"
          placeholder="검색"
          class="mb-1.5 w-full"
        />
        <p
          v-if="!visibleOptions.length"
          class="px-2 py-3 text-[12px] text-(--sk-ink-muted)"
        >
          값이 없습니다.
        </p>
        <ul
          v-else
          class="max-h-64 space-y-0.5 overflow-y-auto"
        >
          <li
            v-for="opt in visibleOptions"
            :key="opt.value"
            class="flex items-center gap-2 rounded-(--sk-r-nav) px-2 py-1 hover:bg-zinc-500/10"
          >
            <UCheckbox
              :model-value="modelValue.includes(opt.value)"
              @update:model-value="toggle(opt.value)"
            />
            <button
              type="button"
              class="flex min-w-0 flex-1 items-baseline justify-between gap-2 text-left"
              @click="toggle(opt.value)"
            >
              <span class="truncate font-mono text-[11.5px] text-zinc-700 dark:text-zinc-200">{{ opt.value }}</span>
              <span class="shrink-0 font-mono text-[10.5px] text-(--sk-ink-subtle)">{{ opt.count }}</span>
            </button>
          </li>
        </ul>
        <div
          v-if="modelValue.length"
          class="mt-1.5 border-t border-(--sk-border-soft) pt-1.5"
        >
          <UButton
            color="neutral"
            variant="ghost"
            size="xs"
            label="선택 해제"
            block
            @click="emit('update:modelValue', [])"
          />
        </div>
      </div>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import type { MeasHistFacetValue } from '~/composables/useMeasHistApi'

const props = defineProps<{
  label: string
  options: MeasHistFacetValue[]
  modelValue: string[]
  // Recipe lists run to hundreds in the office index — type to narrow.
  searchable?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const filterText = ref('')

const visibleOptions = computed(() => {
  const needle = filterText.value.trim().toLowerCase()
  if (!needle) return props.options
  return props.options.filter(o => o.value.toLowerCase().includes(needle))
})

const summary = computed(() => {
  if (!props.modelValue.length) return 'ALL'
  if (props.modelValue.length === 1) return props.modelValue[0]
  return `${props.modelValue.length}개`
})

const toggle = (value: string) => {
  const next = props.modelValue.includes(value)
    ? props.modelValue.filter(v => v !== value)
    : [...props.modelValue, value]
  emit('update:modelValue', next)
}
</script>
```

- [ ] **Step 2: `SearchBar.vue`**

```vue
<template>
  <div>
    <p class="mb-2 px-0.5 text-[11px] text-(--sk-ink-muted)">
      검색 · <span class="font-semibold text-zinc-600 dark:text-zinc-300">장비 / Recipe / Lot / 날짜 / MSR</span>
      · OpenSearch · 최근 {{ retentionDays }}일 보존
    </p>
    <div class="flex items-center gap-2">
      <UInput
        :model-value="modelValue"
        class="flex-1"
        icon="i-lucide-search"
        placeholder="ECXDX925, 6LD257421, ADI_CD_BIAS_001, 2026-05-10 …"
        size="md"
        :loading="pending"
        @update:model-value="emit('update:modelValue', String($event))"
        @keydown.enter="emit('search')"
      />
      <UButton
        class="bg-(--sk-ink) text-(--sk-ink-fg)"
        label="Search"
        icon="i-lucide-corner-down-left"
        size="md"
        :loading="pending"
        @click="emit('search')"
      />
    </div>

    <!-- How each token was read. Without this, auto-detection is a black box
         and a typo is indistinguishable from a genuine no-hit. -->
    <div
      v-if="chips.length"
      class="mt-2 flex flex-wrap items-center gap-1.5"
    >
      <span
        v-for="chip in chips"
        :key="`${chip.field}:${chip.value}`"
        class="inline-flex h-6 items-center gap-1 rounded-(--sk-r-chip) px-2 font-mono text-[11px]"
        :class="chip.field === 'unknown'
          ? 'bg-(--sk-bad)/10 text-(--sk-bad)'
          : 'bg-(--sk-chip-bg) text-(--sk-chip-text)'"
      >
        <span class="opacity-60">{{ chip.label }}</span>
        {{ chip.value }}
        <button
          type="button"
          class="opacity-60 hover:opacity-100"
          @click="emit('update:modelValue', removeToken(modelValue, chip.value))"
        >
          <UIcon
            name="i-lucide-x"
            class="h-3 w-3"
          />
        </button>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ParsedQuery } from '~/utils/measHistQuery'
import { removeToken } from '~/utils/measHistQuery'

const props = defineProps<{
  modelValue: string
  parsed: ParsedQuery
  pending?: boolean
  retentionDays: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'search': []
}>()

const LABELS: Record<string, string> = {
  eq: 'EQ',
  lot: 'LOT',
  recipe: 'RECIPE',
  msr: 'MSR',
  date: 'DATE',
  unknown: '?'
}

const chips = computed(() =>
  (Object.keys(LABELS) as (keyof ParsedQuery)[]).flatMap(field =>
    props.parsed[field].map(value => ({ field, value, label: LABELS[field]! }))
  )
)
</script>
```

- [ ] **Step 3: `FilterBar.vue`**

`Area` is gone — no backing field exists in `sem_list` or `meas_hist`. The 기간 facet reuses the existing `EbeamDateRangePopover` with `anchorDate` so its presets land inside the mock's data window.

```vue
<template>
  <div class="mt-3 flex flex-wrap items-center gap-2">
    <span class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">FILTERS</span>

    <EbeamSkewvoirSearchFacetSelect
      label="FAB"
      :options="facets.fab"
      :model-value="filters.fab"
      :disabled="disabled"
      @update:model-value="patch('fab', $event)"
    />
    <EbeamSkewvoirSearchFacetSelect
      label="장비 종류"
      :options="facets.model"
      :model-value="filters.model"
      :disabled="disabled"
      @update:model-value="patch('model', $event)"
    />
    <EbeamSkewvoirSearchFacetSelect
      label="EQ"
      :options="eqOptions"
      :model-value="filters.eq"
      :disabled="disabled"
      searchable
      @update:model-value="patch('eq', $event)"
    />
    <EbeamSkewvoirSearchFacetSelect
      label="RECIPE"
      :options="facets.recipe"
      :model-value="filters.recipe"
      :disabled="disabled"
      searchable
      @update:model-value="patch('recipe', $event)"
    />

    <EbeamDateRangePopover
      v-if="anchor"
      :model-value="range"
      :anchor-date="anchor"
      @update:model-value="setRange"
    />

    <UButton
      v-if="hasActive"
      color="neutral"
      variant="ghost"
      size="xs"
      icon="i-lucide-rotate-ccw"
      label="초기화"
      @click="emit('reset')"
    />
  </div>
</template>

<script setup lang="ts">
import type { MeasHistFacets } from '~/composables/useMeasHistApi'
import type { MeasHistFilters } from '~/composables/useMeasHistSearch'

const props = defineProps<{
  filters: MeasHistFilters
  facets: MeasHistFacets
  disabled?: boolean
  // Backend-declared clock. Presets resolve against it, not wall-clock today.
  anchor: string
  retentionDays: number
  defaultRange: { start: string, end: string }
}>()

const emit = defineEmits<{
  'update:filters': [value: MeasHistFilters]
  'reset': []
}>()

const patch = <K extends keyof MeasHistFilters>(key: K, value: MeasHistFilters[K]) => {
  emit('update:filters', { ...props.filters, [key]: value })
}

// EQ narrows to the FAB / model already chosen — a tool list of hundreds is
// unusable, and offering equipment that cannot match is just noise.
const eqOptions = computed(() => {
  const { fab, model } = props.filters
  if (!fab.length && !model.length) return props.facets.eq
  // The facet list carries no fab/model linkage, so narrow by prefix agreement
  // is impossible; fall back to the full list when a cross-filter is active.
  return props.facets.eq
})

const range = computed(() => ({
  start: props.filters.from || props.defaultRange.start,
  end: props.filters.to || props.defaultRange.end
}))

const setRange = (value: { start: string, end: string }) => {
  emit('update:filters', { ...props.filters, from: value.start, to: value.end })
}

const hasActive = computed(() =>
  props.filters.fab.length > 0
  || props.filters.model.length > 0
  || props.filters.eq.length > 0
  || props.filters.recipe.length > 0
  || Boolean(props.filters.from)
  || Boolean(props.filters.to)
)
</script>
```

**Note on `eqOptions`:** the facets response returns flat lists with no fab→eq linkage, so the spec's "EQ narrows by FAB/모델" cannot be honoured from the current payload. Two honest options — pick one and do it, do not leave the dead computed above:

1. **Simplest (do this):** drop the `eqOptions` computed entirely and bind `:options="facets.eq"`. The EQ list is searchable, so it stays usable.
2. If narrowing matters, extend `get_meas_hist_facets` to emit `eq` entries as `{ value, count, fab, model }` and filter client-side. That is a backend change; only take it if step 1 proves annoying in the E2E pass.

- [ ] **Step 4: Adjust the DateRangePopover presets**

`DateRangePopover.vue` presets are `Today / 7 / 30 / 90 days`. 90 exceeds retention. Change the preset list to match the window:

```ts
const presets = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 60 days', days: 60 }
]
```

Check the other `EbeamDateRangePopover` consumers first (`CompareTrendCharts.vue`, `FailIssueView.vue`, `RecipeTatView.vue`): if any depends on `Today` or `90 days`, make the preset list a prop with the current list as the default instead of changing it globally.

- [ ] **Step 5: Lint**

Run: `npm --prefix front-dev-home run lint`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/search front-dev-home/app/components/ebeam/DateRangePopover.vue
git commit -m "feat(skewvoir): search bar with parsed-token chips + working facet dropdowns"
```

---

## Task 7: Result table + recently-viewed components

**Files:**

- Create: `front-dev-home/app/components/ebeam/skewvoir/search/ResultTable.vue`
- Create: `front-dev-home/app/components/ebeam/skewvoir/search/RecentlyViewed.vue`

**Interfaces:**

- Consumes: `MeasHistRow`, `SkewvoirRecentEntry`.
- Produces:
  - `ResultTable` props `{ rows: MeasHistRow[], total: number, capped: boolean, outOfRetention: boolean, searched: boolean, pending: boolean, error: string | null, hasMore: boolean, narrowText: string, retentionDays: number }`, emits `open` (`MeasHistRow`), `openSet` (`MeasHistRow[]`), `loadMore`, `retry`, `update:narrowText`
  - `RecentlyViewed` props `{ items: SkewvoirRecentEntry[] }`, emits `open` (`SkewvoirRecentEntry`), `remove` (`string`), `clear`

- [ ] **Step 1: `ResultTable.vue`**

```vue
<template>
  <section class="dashboard-surface flex flex-col rounded-(--sk-r-card)">
    <header class="flex flex-wrap items-center justify-between gap-2 border-b border-(--sk-border-soft) px-3 py-2">
      <div class="flex items-baseline gap-2">
        <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
          검색 결과
        </h2>
        <span
          v-if="searched"
          class="font-mono text-[10.5px] text-(--sk-ink-subtle)"
        >
          {{ rows.length }} / {{ total.toLocaleString() }}건
        </span>
      </div>

      <div
        v-if="selected.length"
        class="flex items-center gap-2"
      >
        <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ selected.length }} 선택</span>
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          label="지우기"
          @click="selected = []"
        />
        <UButton
          class="bg-(--sk-ink) text-(--sk-ink-fg)"
          size="xs"
          icon="i-lucide-trending-up"
          label="선택 분석 (Time-Series)"
          @click="emitSet"
        />
      </div>
      <UInput
        v-else-if="searched && rows.length"
        :model-value="narrowText"
        size="xs"
        icon="i-lucide-filter"
        placeholder="결과 내 좁히기"
        class="w-48"
        @update:model-value="emit('update:narrowText', String($event))"
      />
    </header>

    <!-- The result set exceeded OpenSearch's retrieval ceiling. Hiding this
         would quietly give a wrong answer to "how many times did this run". -->
    <p
      v-if="capped"
      class="border-b border-(--sk-border-soft) bg-amber-500/10 px-3 py-1.5 text-[11.5px] text-amber-700 dark:text-amber-400"
    >
      {{ total.toLocaleString() }}건 중 상위 10,000건만 조회됩니다. 검색어나 기간을 좁혀주세요.
    </p>

    <div
      v-if="error"
      class="flex items-center justify-center gap-3 px-4 py-10 text-[12px] text-(--sk-bad)"
    >
      {{ error }}
      <UButton
        color="neutral"
        variant="outline"
        size="xs"
        label="재시도"
        @click="emit('retry')"
      />
    </div>

    <div
      v-else-if="pending && !rows.length"
      class="flex items-center justify-center gap-2 px-4 py-12 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      검색 중입니다.
    </div>

    <!-- Default state: no query yet. -->
    <div
      v-else-if="!searched"
      class="flex flex-col items-center gap-1.5 px-4 py-14 text-center"
    >
      <UIcon
        name="i-lucide-search"
        class="h-5 w-5 text-(--sk-ink-subtle)"
      />
      <p class="text-[12.5px] text-(--sk-ink-muted)">
        장비 · Recipe · Lot · 날짜 · MSR 로 측정을 검색하세요.
      </p>
      <p class="font-mono text-[10.5px] text-(--sk-ink-subtle)">
        최근 {{ retentionDays }}일 보존
      </p>
    </div>

    <div
      v-else-if="outOfRetention"
      class="flex flex-col items-center gap-1.5 px-4 py-14 text-center"
    >
      <UIcon
        name="i-lucide-calendar-off"
        class="h-5 w-5 text-(--sk-ink-subtle)"
      />
      <p class="text-[12.5px] text-(--sk-ink-muted)">
        보존 기간({{ retentionDays }}일) 밖입니다. 기간을 조정해 주세요.
      </p>
    </div>

    <div
      v-else-if="!rows.length"
      class="flex flex-col items-center gap-1.5 px-4 py-14 text-center"
    >
      <UIcon
        name="i-lucide-file-question"
        class="h-5 w-5 text-(--sk-ink-subtle)"
      />
      <p class="text-[12.5px] text-(--sk-ink-muted)">
        일치하는 측정이 없습니다.
      </p>
    </div>

    <template v-else>
      <table class="w-full border-collapse text-[12px]">
        <thead>
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            <th class="w-8 px-3 py-1.5" />
            <th class="px-3 py-1.5 font-medium">
              LOT
            </th>
            <th class="px-3 py-1.5 font-medium">
              RECIPE
            </th>
            <th class="px-3 py-1.5 font-medium">
              EQ
            </th>
            <th class="px-3 py-1.5 font-medium">
              FAB
            </th>
            <th class="px-3 py-1.5 font-medium">
              CAPTURED
            </th>
            <th class="px-3 py-1.5" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.msr"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0 hover:bg-(--sk-brand)/5"
            :class="{ 'bg-(--sk-brand)/5': selected.includes(row.msr) }"
            @click="emit('open', row)"
          >
            <td
              class="px-3 py-2"
              @click.stop
            >
              <UCheckbox
                :model-value="selected.includes(row.msr)"
                @update:model-value="toggle(row.msr)"
              />
            </td>
            <td class="px-3 py-2 font-mono font-semibold text-zinc-900 dark:text-zinc-100">
              {{ row.lot_id }}
            </td>
            <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
              {{ row.full_name }}
            </td>
            <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
              {{ row.eqp_id }}
            </td>
            <td class="px-3 py-2">
              <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-1.5 py-0.5 font-mono text-[11px] text-(--sk-chip-text)">
                {{ row.fab_name }}
              </span>
            </td>
            <td class="px-3 py-2 font-mono text-(--sk-ink-muted)">
              {{ row.timestamp.slice(0, 16).replace('T', ' ') }}
            </td>
            <td class="px-3 py-2 text-right">
              <UIcon
                name="i-lucide-arrow-right"
                class="h-3.5 w-3.5 text-(--sk-ink-subtle)"
              />
            </td>
          </tr>
        </tbody>
      </table>

      <div
        v-if="hasMore"
        class="border-t border-(--sk-border-soft) p-2"
      >
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          block
          :loading="pending"
          label="더 보기"
          @click="emit('loadMore')"
        />
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { MeasHistRow } from '~/composables/useMeasHistApi'

const props = defineProps<{
  rows: MeasHistRow[]
  total: number
  capped: boolean
  outOfRetention: boolean
  searched: boolean
  pending: boolean
  error: string | null
  hasMore: boolean
  narrowText: string
  retentionDays: number
}>()

const emit = defineEmits<{
  'open': [row: MeasHistRow]
  'openSet': [rows: MeasHistRow[]]
  'loadMore': []
  'retry': []
  'update:narrowText': [value: string]
}>()

const selected = ref<string[]>([])

const toggle = (msr: string) => {
  selected.value = selected.value.includes(msr)
    ? selected.value.filter(m => m !== msr)
    : [...selected.value, msr]
}

const emitSet = () => {
  const picked = props.rows.filter(r => selected.value.includes(r.msr))
  if (picked.length) emit('openSet', picked)
}

// A fresh result set invalidates the old selection.
watch(() => props.rows, () => {
  selected.value = selected.value.filter(msr => props.rows.some(r => r.msr === msr))
})
</script>
```

- [ ] **Step 2: `RecentlyViewed.vue`**

```vue
<template>
  <section class="dashboard-surface flex flex-col rounded-(--sk-r-card)">
    <header class="flex items-center justify-between gap-2 border-b border-(--sk-border-soft) px-3 py-2">
      <div class="flex items-baseline gap-2">
        <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
          최근 본 측정
        </h2>
        <span class="font-mono text-[10.5px] text-(--sk-ink-subtle)">{{ items.length }}</span>
      </div>
      <UButton
        v-if="items.length"
        color="neutral"
        variant="ghost"
        size="xs"
        label="전체 삭제"
        @click="emit('clear')"
      />
    </header>

    <p
      v-if="!items.length"
      class="px-4 py-10 text-center text-[12px] text-(--sk-ink-muted)"
    >
      아직 연 측정이 없습니다. 검색 결과에서 측정을 열면 여기에 쌓입니다.
    </p>

    <table
      v-else
      class="w-full border-collapse text-[12px]"
    >
      <tbody>
        <tr
          v-for="item in items"
          :key="item.msr"
          class="group border-b border-(--sk-border-soft) transition-colors last:border-0"
          :class="item.expired
            ? 'cursor-not-allowed opacity-50'
            : 'cursor-pointer hover:bg-(--sk-brand)/5'"
          @click="!item.expired && emit('open', item)"
        >
          <td class="px-3 py-2 font-mono font-semibold text-zinc-900 dark:text-zinc-100">
            {{ item.lot }}
          </td>
          <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
            {{ item.recipe }}
          </td>
          <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
            {{ item.eq }}
          </td>
          <td class="px-3 py-2 font-mono text-(--sk-ink-muted)">
            {{ item.capturedAt.slice(0, 10) }}
          </td>
          <td class="px-3 py-2">
            <!-- Remembered, but the data is gone. Saying so beats silently
                 dropping a row the user knows they looked at. -->
            <span
              v-if="item.expired"
              class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-1.5 py-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)"
            >
              보존 기간 만료
            </span>
          </td>
          <td
            class="px-3 py-2 text-right"
            @click.stop
          >
            <button
              type="button"
              class="opacity-0 transition-opacity group-hover:opacity-100"
              @click="emit('remove', item.msr)"
            >
              <UIcon
                name="i-lucide-x"
                class="h-3.5 w-3.5 text-(--sk-ink-muted) hover:text-(--sk-bad)"
              />
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import type { SkewvoirRecentEntry } from '~/composables/useSkewvoirRecentlyViewed'

defineProps<{
  items: SkewvoirRecentEntry[]
}>()

const emit = defineEmits<{
  'open': [item: SkewvoirRecentEntry]
  'remove': [msr: string]
  'clear': []
}>()
</script>
```

- [ ] **Step 3: Lint**

Run: `npm --prefix front-dev-home run lint`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/search
git commit -m "feat(skewvoir): result table + recently-viewed table"
```

---

## Task 8: Rewire `SearchLanding.vue` and delete the dead surface

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/SearchLanding.vue` (full rewrite)
- Modify: `front-dev-home/app/composables/useSkewvoirWorkspace.ts`
- Modify: any `pinnedFilters` consumer (check with grep)
- Modify: `front-dev-home/app/pages/ebeam/cd-sem/skewvoir/analysis.vue`, `.../hv-sem/skewvoir/analysis.vue`

- [ ] **Step 1: Find every `pinnedFilters` consumer before deleting it**

```bash
grep -rn "pinnedFilters\|SkewvoirPinnedFilters" front-dev-home/app
```

Expected: `useSkewvoirWorkspace.ts` (declaration + return), `SearchLanding.vue`, and possibly `workspace/LeftRail.vue`. Remove the state, its type, and every read. If `LeftRail.vue` renders the pinned filters as a rail section, delete that section — it was mock-seeded and never reflected a real query.

- [ ] **Step 2: Rewrite `SearchLanding.vue`**

```vue
<template>
  <div class="space-y-4">
    <!-- Landing header -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="font-mono text-[11px] tracking-wide text-(--sk-ink-subtle)">
          {{ toolLabel }} · SKEWVOIR
        </p>
        <h1 class="mt-0.5 text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          측정 결과 검색
        </h1>
        <p class="mt-1 text-[12.5px] text-(--sk-ink-muted)">
          Lot · Recipe · 장비 · 날짜 · MSR 로 측정을 찾고, 결과를 열면 분석 워크스페이스로 이동합니다.
        </p>
      </div>

      <!-- Saved views -->
      <UPopover>
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-bookmark"
          :label="`저장된 뷰 ${savedViews.views.value.length}`"
          size="sm"
        />
        <template #content>
          <div class="w-80 p-2">
            <p class="px-2 py-1 font-mono text-[10px] font-semibold tracking-wider text-(--sk-ink-muted)">
              SAVED VIEWS
            </p>
            <p
              v-if="!savedViews.views.value.length"
              class="px-2 py-3 text-[12px] text-(--sk-ink-muted)"
            >
              저장된 뷰가 없습니다. 분석 화면에서 “Save view”로 저장하세요.
            </p>
            <ul
              v-else
              class="max-h-72 space-y-0.5 overflow-y-auto"
            >
              <li
                v-for="v in savedViews.views.value"
                :key="v.id"
                class="group flex items-center gap-2 rounded-(--sk-r-nav) px-2 py-1.5 hover:bg-zinc-500/10"
              >
                <button
                  type="button"
                  class="min-w-0 flex-1 text-left"
                  @click="openSaved(v)"
                >
                  <span class="block truncate text-[12.5px] font-medium text-zinc-800 dark:text-zinc-100">{{ v.name }}</span>
                  <span class="block truncate font-mono text-[10.5px] text-(--sk-ink-subtle)">{{ String(v.query.lot ?? '') }}</span>
                </button>
                <button
                  type="button"
                  class="opacity-0 transition-opacity group-hover:opacity-100"
                  @click="savedViews.remove(v.id)"
                >
                  <UIcon
                    name="i-lucide-x"
                    class="h-3.5 w-3.5 text-(--sk-ink-muted) hover:text-(--sk-bad)"
                  />
                </button>
              </li>
            </ul>
          </div>
        </template>
      </UPopover>
    </div>

    <!-- Search + filters -->
    <div class="dashboard-surface rounded-(--sk-r-card) p-3">
      <EbeamSkewvoirSearchSearchBar
        v-model="search.queryText.value"
        :parsed="search.parsed.value"
        :pending="search.pending.value"
        :retention-days="search.retentionDays.value"
        @search="search.search"
      />
      <EbeamSkewvoirSearchFilterBar
        :filters="search.filters.value"
        :facets="search.facets.value!"
        :disabled="search.facetsPending.value"
        :anchor="search.anchor.value"
        :retention-days="search.retentionDays.value"
        :default-range="search.defaultRange.value"
        @update:filters="search.filters.value = $event"
        @reset="search.resetFilters"
      />
    </div>

    <!-- Results -->
    <EbeamSkewvoirSearchResultTable
      :rows="search.narrowedRows.value"
      :total="search.total.value"
      :capped="search.capped.value"
      :out-of-retention="search.outOfRetention.value"
      :searched="search.searched.value"
      :pending="search.pending.value"
      :error="search.error.value"
      :has-more="search.hasMore.value"
      :narrow-text="search.narrowText.value"
      :retention-days="search.retentionDays.value"
      @update:narrow-text="search.narrowText.value = $event"
      @open="open"
      @open-set="openSet"
      @load-more="search.loadMore"
      @retry="search.search"
    />

    <!-- Recently viewed (localStorage) -->
    <EbeamSkewvoirSearchRecentlyViewed
      :items="recent.items.value"
      @open="openRecent"
      @remove="recent.remove"
      @clear="recent.clear"
    />
  </div>
</template>

<script setup lang="ts">
import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { SkewvoirRecentEntry } from '~/composables/useSkewvoirRecentlyViewed'
import type { SkewvoirSavedView } from '~/composables/useSkewvoirSavedViews'
import type { SkewvoirSelection } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{
  toolLabel: string
  toolType: MeasHistToolType
}>()

const ws = useSkewvoirWorkspace(props.toolType, props.toolLabel)
const savedViews = useSkewvoirSavedViews(props.toolType)
const search = useMeasHistSearch(props.toolType)
const recent = useSkewvoirRecentlyViewed(props.toolType)
const router = useRouter()

// Expiry in the recently-viewed list is judged against the backend's retention
// anchor, not wall clock.
watch(search.anchor, value => recent.setAnchor(value), { immediate: true })

const toSelection = (row: MeasHistRow): SkewvoirSelection => ({
  lot: row.lot_id,
  recipe: row.recipe_name,
  eq: row.eqp_id,
  mp: 'WAFER',
  msr: row.msr,
  capturedAt: row.timestamp
})

const open = (row: MeasHistRow) => {
  recent.record({
    msr: row.msr,
    toolType: props.toolType,
    lot: row.lot_id,
    recipe: row.full_name,
    eq: row.eqp_id,
    fab: row.fab_name,
    capturedAt: row.timestamp,
    viewedAt: new Date().toISOString()
  })
  ws.openAnalysis(toSelection(row))
}

const openSet = (rows: MeasHistRow[]) => {
  const first = rows[0]
  if (!first) return
  ws.openAnalysisSet(toSelection(first), rows.map(r => r.msr), 'time-series')
}

const openRecent = (item: SkewvoirRecentEntry) => {
  ws.openAnalysis({
    lot: item.lot,
    recipe: item.recipe.includes('/') ? item.recipe.split('/')[1]! : item.recipe,
    eq: item.eq,
    mp: 'WAFER',
    msr: item.msr,
    capturedAt: item.capturedAt
  })
}

const openSaved = (v: SkewvoirSavedView) =>
  router.push({ path: ws.analysisPath, query: v.query })
</script>
```

- [ ] **Step 3: Record recently-viewed when analysis is opened by link**

A shared analysis link bypasses the landing page, so record there too. In each of `pages/ebeam/cd-sem/skewvoir/analysis.vue` and `pages/ebeam/hv-sem/skewvoir/analysis.vue`, read the existing selection source (`useSkewvoirRoute(...).selection`) and record it once on mount. Read the file first to match its existing composable wiring, then add:

```ts
const recent = useSkewvoirRecentlyViewed('cd-sem') // 'hv-sem' in the hv page
const { anchor } = useMeasHistFacets('cd-sem')

watch(anchor, value => recent.setAnchor(value), { immediate: true })

onMounted(() => {
  const sel = selection.value
  if (!sel?.msr) return
  recent.record({
    msr: sel.msr,
    toolType: 'cd-sem',
    lot: sel.lot,
    recipe: sel.recipe,
    eq: sel.eq,
    fab: '',
    capturedAt: sel.capturedAt,
    viewedAt: new Date().toISOString()
  })
})
```

If the analysis page delegates entirely to a `Workspace.vue` component and has no access to `selection`, put this in `Workspace.vue` instead — it already consumes `useSkewvoirWorkspace`. Do whichever matches the existing structure; do not duplicate the call in both.

- [ ] **Step 4: Lint and test**

Run: `npm --prefix front-dev-home run lint && npm --prefix front-dev-home test`
Expected: no errors, all tests pass.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app
git commit -m "feat(skewvoir): wire search landing to real search; drop placeholder panels"
```

---

## Task 9: End-to-end verification

**Files:** none — this task changes nothing unless it finds a defect.

- [ ] **Step 1: Start both servers**

```bash
.venv/bin/python -m flask --app index run --port 5000
npm --prefix front-dev-home run dev
```

- [ ] **Step 2: Drive the page**

Open `http://localhost:3000/ebeam/cd-sem/skewvoir` and verify each claim. Screenshots go under `.playwright-mcp/screenshots/`.

1. **Empty state** — the results panel shows the "장비 · Recipe · Lot · 날짜 · MSR 로 측정을 검색하세요" prompt. No Result Timeline, no Quick Stats, no `MP : WAFER` / `3σ` / `outliers` chips.
2. **Dropdowns open** — click FAB. A popover appears with real fab values and counts. This is the bug the user reported ("I do not see the dropbox here"); if nothing opens, the task is not done.
3. **Search by equipment** — type a real `eqp_id` from the FAB dropdown, press Enter. A chip reads `EQ <id>`; results contain only that tool.
4. **Multiple tokens OR within a field** — `<eq1>, <eq2>` returns rows from both tools (this is the comma/semicolon tokenizer and the OR rule).
5. **Unknown token** — type `zzz`; a red `? zzz` chip appears and the result is 일치하는 측정이 없습니다.
6. **Date** — type `date:2026-05-10`; results are that day only.
7. **기간 dropdown** — presets land inside the data window (not an empty result). If a preset yields zero rows, the anchor wiring is broken.
8. **Open a row** — it navigates to the analysis workspace.
9. **Back to search** — the row now appears under 최근 본 측정.
10. **Cap at 15** — open 16 different measurements; the list holds the newest 15.
11. **Expiry** — in devtools, edit one `skewvoir-recently-viewed` entry's `capturedAt` to `2026-01-01`, reload: that row is greyed with `보존 기간 만료` and is not clickable.

- [ ] **Step 3: Repeat the smoke check on hv-sem**

Open `http://localhost:3000/ebeam/hv-sem/skewvoir`, confirm facets and search return hv-sem rows only.

- [ ] **Step 4: Fix anything broken, then commit**

```bash
git add -A
git commit -m "fix(skewvoir): E2E verification fixes"
```

---

## Self-Review Notes

- **Spec §4 (grammar)** → Task 1. **§5 (backend)** → Task 2. **§5.2.1 (anchor)** → Task 2 step 1 + Task 3 (`anchor` in facets) + Task 4 (`defaultRange`) + Task 5 (expiry). **§6.1 (composables)** → Tasks 3–5. **§6.2–6.4 (components)** → Tasks 6–7. **§6.5 (recently viewed)** → Tasks 5, 7, 8. **§6.6 (deletions)** → Task 8. **§7 (errors)** → Task 7 (`ResultTable` error / empty / capped / out-of-retention branches) + Task 6 (`disabled` facets). **§8 (testing)** → Task 1 + Task 2 step 3 + Task 9.
- **Known loose end, flagged in Task 6 step 3:** the spec says the EQ dropdown narrows by the selected FAB/모델, but the facets payload has no fab→eq linkage. The plan tells the implementer to bind the flat list (EQ is searchable) and only extend the backend if the E2E pass shows it matters. Do not leave the dead `eqOptions` computed in place.
- **Type consistency:** `ParsedQuery` / `KnownValues` (Task 1) are consumed by Tasks 3, 4, 6. `MeasHistFilters` (Task 4) by Task 6. `SkewvoirRecentEntry` (Task 5) by Task 7. `MeasHistSearchResponse.range.anchor` (Tasks 2–3) feeds `defaultRange` (Task 4) and `setAnchor` (Task 5).
