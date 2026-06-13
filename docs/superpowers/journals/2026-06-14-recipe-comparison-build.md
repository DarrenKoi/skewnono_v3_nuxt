# Recipe Comparison — Build Journal & Code-Review Handoff

- **Date:** 2026-06-14
- **Status:** Implemented, reviewed (per-task spec + quality), Playwright-verified end-to-end. **Merged to `main` (fast-forward, commit `f4b19aa`); branch `feat/recipe-comparison` deleted. NOT pushed to `origin/main` yet.**
- **Spec:** `docs/superpowers/specs/2026-06-14-recipe-comparison-design.md`
- **Plans:** `docs/superpowers/plans/2026-06-14-recipe-comparison-INDEX.md` (+ plan1/plan2/plan3)
- **Tests:** 65 `node --test` cases pass · `nuxt typecheck` clean · `npm run lint` clean (no new errors)
- **Purpose of this file:** a self-contained map for a fresh code-review session — what was built, where it lives, what to scrutinize, and how to verify.

---

## 1. What was built (one paragraph)

A recipe comparison service at `/ebeam/{cd-sem,hv-sem}/<fab>/recipe-search/compare`. Engineers
multi-select recipes on the existing search page (a persistent "working set"), then compare them:
an **overlap grid** (which parameters exist in which recipes) drilling into a **parameter attribute
matrix** with **slot tabs** (3 addressing + 2 measure image slots), **image thumbnails + lightbox**,
a **나란히 (side-by-side) ⇄ 분포 (value-grouping/outlier)** view toggle, a **차이만 보기**
(differences-only) filter, and **client-side Excel export**. Targets ~100 recipes via one batch
backend request + pure client-side derivations.

## 2. Suggested reading order for review

1. `docs/superpowers/specs/2026-06-14-recipe-comparison-design.md` — the approved design (the "why").
2. `back_dev_home/ebeam/hitachi/recipe_search/data.py` → `get_recipe_compare_data` — the data contract source.
3. `front-dev-home/app/composables/useRecipeCompareApi.ts` — the TS types mirroring that contract.
4. `front-dev-home/app/utils/recipeCompare.ts` + `recipeCompare.test.ts` — **all the logic + its tests** (review this most carefully).
5. `front-dev-home/app/composables/useRecipeSelectionSet.ts` — the working-set primitive.
6. `front-dev-home/app/components/ebeam/RecipeCompareView.vue` — the orchestrator (ties everything together).
7. The five `components/ebeam/recipeCompare/*` children + the `RecipeSearchView.vue` diff.

## 3. File inventory

### Created — backend (Flask mock)

None created; both backend files were modified (see below).

### Created — frontend logic / state

| File | Lines | Purpose | Review hotspots |
| --- | --- | --- | --- |
| `front-dev-home/app/utils/recipeCompare.ts` | ~297 | All pure comparison logic: `buildOverlap`/`classifyCoverage`/`filterOverlap`/`commonParameters`, `buildIdpRows`/`buildAmpRows`/`cellsDiffer`/`imageFilenames`/`findParameter`, `groupFieldValues`, `buildCompareWorkbook`, `downloadCompareWorkbook`. Also **inlined** slot/AMP metadata (`COMPARE_SLOTS`, `AMP_FIELDS_*`, `ampFieldsForRole`, `formatAmpValue`) mirrored from `recipeView.ts`. | The inlined block must stay in sync with `recipeView.ts` (see §6.2). Outlier rule in `groupFieldValues` (§6.4). `downloadCompareWorkbook` is the only browser-only fn (dynamic `import('xlsx')`), not unit-tested. |
| `front-dev-home/app/utils/recipeCompare.test.ts` | ~179 | 65 `node --test` cases over the pure fns above. | Confirms behavior; note `downloadCompareWorkbook` is intentionally untested (lib + DOM). |
| `front-dev-home/app/composables/useRecipeCompareApi.ts` | ~76 | `fetchCompare()` → POSTs the batch compare endpoint; in-flight dedup keyed on sorted names. Exports the `Compare*`/`RecipeCompareResponse` TS types. | Type shape must match backend JSON exactly (§5). |
| `front-dev-home/app/composables/useRecipeSelectionSet.ts` | ~79 | Persistent working set per `(toolType, fab)`: `useState` ref + `effectScope` watcher → `localStorage`. Returns `selected/has/add/remove/toggle/clear/count`. Mirrors `useRecipeRecentSearches.ts`. | Reassignment (not mutation) of `selected.value`; single watcher per scope. |

### Created — frontend components

| File | Lines | Auto-import name | Purpose |
| --- | --- | --- | --- |
| `front-dev-home/app/components/ebeam/RecipeCompareView.vue` | ~244 | `EbeamRecipeCompareView` | Page orchestrator: reads working set, fetches via `useAsyncData`, owns parameter tabs / slot tabs / view-mode / diff-only, renders all children + loading/error/empty states. |
| `front-dev-home/app/components/ebeam/recipeCompare/ParameterSelector.vue` | ~163 | `EbeamRecipeCompareParameterSelector` | Parameter search + coverage filter chips (전체/공통/부분/고유) + overlap table (checkbox per row, coverage tag, ✓/— presence) + 공통 전체 선택. `v-model` = selected parameter names. |
| `front-dev-home/app/components/ebeam/recipeCompare/CompareMatrix.vue` | ~138 | `EbeamRecipeCompareMatrix` *(NOT …CompareMatrix — see §6.1)* | 나란히 view: IDP block + slot AMP block + thumbnail row (reuses `recipeOpen/ImgThumb` + `ImageLightbox`); diff rows highlighted. |
| `front-dev-home/app/components/ebeam/recipeCompare/CompareGrouping.vue` | ~93 | `EbeamRecipeCompareGrouping` *(NOT …CompareGrouping)* | 분포 view: per-field value buckets with outlier (⚠) styling; click a bucket → lists deviating recipe ids. |
| `front-dev-home/app/components/ebeam/recipeCompare/RecipeSetBar.vue` | ~113 | `EbeamRecipeCompareRecipeSetBar` | Working-set chips (× to remove) + inline type-ahead add (backed by the shared recipe catalog) + Excel download button. |
| `front-dev-home/app/components/ebeam/recipeCompare/SearchSelectTray.vue` | ~97 | `EbeamRecipeCompareSearchSelectTray` | Sticky bottom tray on the search page: chips + count + 열어보기/횡전개/측정이력/비교하기. Presentational (typed emits only). |

### Created — frontend pages (thin route wrappers)

| File | Lines | Purpose |
| --- | --- | --- |
| `front-dev-home/app/pages/ebeam/cd-sem/[fab]/recipe-search/compare.vue` | ~28 | Renders `<EbeamRecipeCompareView tool-type="cd-sem" tool-label="CD-SEM">`; sets nav tool/fab. |
| `front-dev-home/app/pages/ebeam/hv-sem/[fab]/recipe-search/compare.vue` | ~28 | HV-SEM twin. |

### Modified

| File | Δ | What changed | Review note |
| --- | --- | --- | --- |
| `back_dev_home/ebeam/hitachi/recipe_search/data.py` | +70 | Added `COMPARE_IDP_FIELDS`, `CompareParameter`/`CompareRecipe`/`RecipeCompareResponse` TypedDicts, `get_recipe_compare_data()` (reuses `get_recipe_open_data`, dedupes params, projects IDP+images+amp). | Dedupe edge: a parameter repeated in `idp_image_info` keeps the first; its amp rows then include duplicates (first-per-slot wins downstream). |
| `back_dev_home/ebeam/hitachi/recipe_search/routes.py` | +~27 | Added `POST /<tool_slug>/recipe-search/compare` (validates non-empty list, caps at 200, reads `fab_name` from JSON body). | Cap = 200 (feature targets ~100). |
| `front-dev-home/app/components/ebeam/RecipeSearchView.vue` | +64 | Added a leading `select` checkbox column (+ page select-all header), the `useRecipeSelectionSet` wiring, the `SearchSelectTray`, the four tray-action handlers, and a discoverability hint. | All pre-existing search/filter/pagination/per-row buttons preserved. Tray 열어보기/횡전개/측정이력 open the **first** selected recipe (compare-first scope). |
| `front-dev-home/package.json` / `package-lock.json` | +3 / +94 | Added `xlsx@^0.18.5` (SheetJS, for client-side export). | Only used to *write* workbooks (no untrusted parsing). |

## 4. Architecture & data flow

```text
Search page (RecipeSearchView.vue)
  └─ checkbox column → useRecipeSelectionSet(toolType, fab)  ── localStorage (per tool×fab)
        selected[] survives query changes & reloads
  └─ SearchSelectTray → 비교하기 → router.push(.../recipe-search/compare)
                                                  │
compare.vue (thin wrapper) → RecipeCompareView.vue (orchestrator)
  ├─ reads the SAME useRecipeSelectionSet → selected[]
  ├─ useAsyncData(key=recipe-compare:<tool>:<fab>:<sorted-names>) → useRecipeCompareApi.fetchCompare()
  │        └─ POST /api/<slug>/recipe-search/compare  →  Flask get_recipe_compare_data()
  ├─ buildOverlap(recipes) → ParameterSelector (overlap grid + coverage filters)
  └─ for the active parameter + slot + view-mode:
        ├─ 나란히 → CompareMatrix  (buildIdpRows / buildAmpRows / imageFilenames + ImgThumb/Lightbox)
        └─ 분포   → CompareGrouping (groupFieldValues → buckets + outlier flag)
        └─ Excel  → buildCompareWorkbook(recipes, params) → downloadCompareWorkbook() [dynamic xlsx]
```

All analytics are **pure client-side functions** in `recipeCompare.ts`; the server does one cheap thing
(return trimmed per-recipe data).

## 5. Data contract (backend JSON ↔ TS types)

Backend `get_recipe_compare_data` returns (and `RecipeCompareResponse` mirrors):

```jsonc
{
  "tool_type": "cd-sem",
  "fab_name": "R3",
  "recipes": [
    {
      "recipe_id": "RACE/DEAE_ABC123_STD_00012",
      "fac_id": "R3",
      "parameters": [
        {
          "Parameter": "WAFER",
          "idp": { "Addressing": "Yes", "Double_Addressing": false, "Mother_Para": "Para_2",
                   "Region": 5, "Meas_Counting": 3, "dnumber_removed": 0 },
          "images": { "img_add1": "...", "img_add2": "...", "image_add3": "...",
                      "img_meas1": "...", "img_meas2": "..." },
          "amp": [ { "parameter": "WAFER", "slot": "img_meas1", "role": "measure", ... }, ... ]
        }
      ]
    }
  ]
}
```

Field names are **identical** across the boundary (capital-`Parameter`, snake_case slot keys). The final
whole-branch review confirmed no field-name mismatch.

## 6. Key decisions & course-corrections (review these)

### 6.1 Nuxt auto-import dedupes the trailing folder/filename overlap (was a bug)
`components/ebeam/recipeCompare/CompareMatrix.vue` registers as **`EbeamRecipeCompareMatrix`** (single
"Compare"), NOT `EbeamRecipeCompareCompareMatrix`. The plan originally specified the double-`Compare`
name → the matrix/grouping silently rendered nothing (`Failed to resolve component`). Fixed in `a4f528f`.
**Verify against `front-dev-home/.nuxt/components.d.ts`.** (Only the *trailing* overlap collapses;
`RecipeSetBar` keeps its `Recipe`.)

### 6.2 A tested util cannot runtime-import a sibling util here
`node --test` can't resolve the `~` alias and needs `.ts` extensions; `nuxt typecheck` forbids `.ts`
extensions (TS5097); type-only imports are erased (safe in both). So `recipeCompare.ts` keeps
`recipeView` imports **type-only** and **inlines** the runtime metadata (`COMPARE_SLOTS`, `AMP_FIELDS_*`,
`ampFieldsForRole`, `formatAmpValue`) with a `KEEP IN SYNC` comment. **Review risk:** drift from
`recipeView.ts` if its AMP field lists change. The final review confirmed they match exactly today.

### 6.3 State-authoritative, not URL
The compare page reads recipes from `useRecipeSelectionSet` (shared `useState`), NOT the URL — 100-name
URLs are impractical. Scoped per `(toolType, fab)`; switching fab shows a different set. No cross-fab compare.

### 6.4 Outlier rule (분포 view)
A value bucket is an outlier when it is **not the single largest** bucket AND its share `count/total ≤ 0.25`
(`OUTLIER_SHARE`). Ties for largest flag nothing. Default view flips to 분포 when recipe count `> 8`
(`GROUPING_DEFAULT_THRESHOLD`). Boundary cases covered by tests.

### 6.5 Compare-first scope (deliberate, deferred work)
Only 비교하기 consumes the full set now. The tray's 열어보기/횡전개/측정이력 open the **first** selected
recipe (existing single-recipe behavior). An in-page **recipe switcher** across those three views is a
documented fast-follow — the set composable is built switcher-ready but the switcher is **not** implemented.

### 6.6 NuxtUI `UCheckbox` must use its `label` prop, not a wrapping `<label>`
Double-label nesting caused a double-toggle / unresponsive checkbox on some browsers. Fixed in `78377c0`.

### 6.7 Excel = client-side (`xlsx`)
`buildCompareWorkbook` (pure, tested) builds a `{ sheets:[{name,rows}] }` shape; `downloadCompareWorkbook`
(dynamic-imports `xlsx`, browser-only) writes it. `xlsx@0.18.5` has npm advisories but we only *write*
workbooks from the user's own loaded data — no untrusted parsing.

## 7. Test coverage map

- **Unit-tested (65 cases, `recipeCompare.test.ts`):** `classifyCoverage`, `buildOverlap` (incl. dedupe),
  `filterOverlap`, `commonParameters`, `cellsDiffer`, `buildIdpRows`, `buildAmpRows` (incl. `없음` path),
  `imageFilenames`, `groupFieldValues` (sort, minority flag, tie, single-value), `buildCompareWorkbook`
  (sheet set/order, headers, cells).
- **Backend verified via `python -c` / Flask test client** (no pytest suite in repo): `get_recipe_compare_data`
  shape + parity with `get_recipe_open_data`; POST success / empty-list 400 / bad-slug 400 / >200 cap 400.
- **NOT unit-tested (by repo convention):** composables (`useRecipeSelectionSet`, `useRecipeCompareApi`) and
  all `.vue` components — verified by `nuxt typecheck` + the Playwright E2E. `downloadCompareWorkbook`
  intentionally untested (lib + DOM).

## 8. How to run / verify

```bash
# from front-dev-home/
npm run test       # 65 pass
npm run typecheck  # clean
npm run lint       # clean except a pre-existing settings/ApiTokens.vue error (unrelated)

# backend (repo root, venv on PATH)
python -c "from back_dev_home import create_app; c=create_app().test_client(); \
print(c.post('/api/cdsem/recipe-search/compare', json={'fab_name':'R3','recipe_names':['ABC/123_MAIN_ABC123_STD_00045','RACE/DEAE_ABC123_STD_00012']}).status_code)"  # 200
```

**E2E (servers: Flask :5050 + Nuxt :3000, both run by the user in PyCharm):**
`/ebeam/cd-sem/r3/recipe-search` → search `ABC`, check 2 → search `RACE`, check 2 → tray shows 4 →
비교하기 → 공통 전체 선택 → matrix renders (IDP + thumbnails + AMP, diffs highlighted) → click thumbnail
(lightbox) → switch slot tabs → 차이만 보기 → 분포 toggle (outlier ⚠, click bucket → recipe ids) →
Excel 다운로드. E2E screenshots saved under `.playwright-mcp/screenshots/` (e.g. `verify3-matrix-fixed.png`).

## 9. Known issues / follow-ups (non-blocking)

1. **Mock AMP data is seeded by parameter NAME only** (`generate_amp_info` → `_seed_for_values("amp", parameter)`),
   so the same parameter has IDENTICAL amp rows across recipes → the AMP matrix/분포 always shows
   *agreement* on mock data; only IDP fields (per-recipe seeded) differ. Real office data will differ.
   **Follow-up:** seed AMP off `(recipe_id + parameter)` to make the mock demo richer.
2. **Recipe switcher** for open/lateral/meas-hist is deferred (§6.5).
3. **Backend `recipe_names` cap = 200** — generous for the ~100 target; revisit if the office Flask reuses
   this handler with different limits.
4. **Branch not pushed** — `main` is ahead of `origin/main`. Push when ready (`git push origin main`).

## 10. Commit map (task → commit, on `main`)

```text
8eb3245 spec
d2c0429 plans (INDEX + 3)
— Plan 1 (data + logic foundation) —
839231d get_recipe_compare_data       869e43e POST /compare endpoint
e7880c2 useRecipeCompareApi           d11538e overlap+coverage util
6fbfb5a matrix rows+diff util         b8d136c fix: inline recipeView metadata (node-test+typecheck safe)
7fbbe40 grouping+outlier util         a966da4 workbook builder util        c848338 style: consolidate test imports
— Plan 2 (selection layer) —
4291e43 useRecipeSelectionSet         0391b3e SearchSelectTray              aeb515d search-view wiring
— Plan 3 (compare view) —
48b9d56 xlsx + download helper        adf0367 ParameterSelector            d9a2e8a CompareMatrix
006d6a4 CompareGrouping               f1e2381 RecipeSetBar                 d4d14a6 RecipeCompareView
78377c0 fix: UCheckbox label          8a9676f page wrappers                a4f528f fix: auto-import names
f4b19aa polish: useAsyncData default + Excel try/catch + 200-recipe cap
```

## 11. Suggested review focus (where bugs are most likely)

- `recipeCompare.ts` ↔ `recipeView.ts` metadata drift (§6.2) — diff `COMPARE_SLOTS`/`AMP_FIELDS_*` against the source.
- `groupFieldValues` outlier semantics (§6.4) at boundaries (ties, all-unique, single value).
- Column/index alignment in `CompareMatrix`/`CompareGrouping`: header `recipeIds` vs per-recipe `values[i]`
  / `images[i]` (all derive from `props.recipes` in order — confirm no reindexing).
- `RecipeSetBar` `useAsyncData` shares the search page's cache key (`recipe-search:<tool>:<fab|ALL>`) — options
  were aligned in `f4b19aa`; confirm deep-linking to `/compare` (no prior search visit) still fetches the catalog.
- `RecipeSearchView.vue` diff — confirm no existing search/filter/pagination/per-row behavior regressed.
