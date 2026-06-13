# Recipe Comparison Service — Design

- **Date:** 2026-06-14
- **Tool families:** CD-SEM, HV-SEM (Hitachi ebeam)
- **Surface:** `/ebeam/<tool>/<fab>/recipe-search/compare`
- **Status:** Design approved, ready for implementation plan

## 1. Problem

The recipe-open service (`recipe-search/open`) lets a user inspect **one** recipe's
parameters and Auto-Meas-Parameter (AMP) settings. Customers now want to **compare
many recipes at once** — selecting recipes and the parameters within them, and reading
how their measurement setups differ. The comparison must scale to roughly **100
recipes**, support a **"differences only"** read, and be **downloadable to Excel**.

## 2. Core Decisions (resolved in brainstorming)

| # | Decision | Choice |
| --- | --- | --- |
| 1 | Comparison shape | Overlap grid first, drill into a parameter's attribute matrix |
| 2 | Assembly | Persistent multi-select **working set** seeded from the search page |
| 3 | First-pass scope | Compare view now; switcher for open/lateral/meas-hist is a fast-follow |
| 4 | Drill-down slot handling | **Slot tabs** (Add 1/2/3, Meas 1/2), one slot focused at a time |
| 5 | Images | Per-slot image thumbnails per recipe, reusing `ImgThumb` + `ImageLightbox` |
| 6 | Large-N strategy | **분포 (grouping/outlier)** view mode, toggleable at any N |
| 7 | Multi-parameter | **Parameter tabs** on screen (one parameter's matrix at a time) |
| 8 | Excel | **Client-side** generation (SheetJS) from the loaded compare payload |
| 9 | Fetching | **Batch compare endpoint** — one request, compact payload |

## 3. Workflow

```text
Search page (existing)                    Compare page (new)
─────────────────────                     ──────────────────
[✓] recipe row  ─┐                         ① Recipe set bar (working set, editable + Excel)
[✓] recipe row   ├─ working set ─────────► ② Parameter selection layer (search + coverage filter)
[ ] recipe row   │  (persists across       ③ Comparison output
 search "ABC"…   │   query changes)            • 나란히 (matrix)  ⇄  분포 (grouping)
[✓] recipe row  ─┘                             • parameter tabs · slot tabs · 차이만 보기
        │
        └─ tray: [열어보기][횡전개][측정이력][비교하기]
```

The user checks recipes on the existing search page; selections **accumulate across
searches** (changing the query does not clear them). A sticky tray surfaces the set and
its actions. "비교하기" opens the compare page against the current set.

## 4. The Working Set (selection layer)

A persistent, per-`(toolType, fab)` set of recipe names — the unifying primitive that
this feature introduces and that open/lateral/meas-hist will later consume.

- **Composable:** `useRecipeSelectionSet(toolType, fab)`, mirroring
  `useRecipeRecentSearches` exactly — `useState` shared ref + `effectScope` watcher
  persisting to `localStorage` under `skewnono:recipe-search.selection.<tool>.<fab>`.
- **API:** `selected` (ref `string[]`), `toggle(name)`, `add(name)`, `remove(name)`,
  `clear()`, `has(name)`, `count`.
- **Scope:** comparison is only meaningful within one `(toolType, fab)` — recipe names
  and parameters are not comparable across tool families. Switching fab/tool exposes a
  separate set (same as recent-searches scoping). No cross-fab comparison in this pass.
- **Source of truth:** the compare page reads the **working-set state**, not the URL.
  At ~100 recipes a URL-encoded list is impractical, so state is authoritative. A
  "공유" affordance can copy the recipe-name list; small sets may still reflect names in
  the query for bookmarkability (best-effort, not required).
- **No hard cap** on count. The UI nudges toward 분포 view past a threshold
  (`GROUPING_DEFAULT_THRESHOLD = 8`).

### Search-page changes

- Add a leading **checkbox column** to the results `UTable`. Existing per-row buttons
  (열어보기/횡전개/측정이력) stay unchanged for the single-recipe quick path.
- A **sticky bottom tray** appears when `count ≥ 1`: selected chips (× to remove),
  count, "선택 비우기", and four action buttons.
- Tray actions in this pass: **비교하기** consumes the full set; 열어보기/횡전개/측정이력
  open the **first** selected recipe (current single-recipe behavior) — the in-page
  recipe switcher across those three views is the documented fast-follow.
- Empty-state hint near the search box: *"체크하면 여러 recipe를 한 번에 열거나 비교할 수 있습니다."*

## 5. Compare Page Layers

### ① Recipe set bar
Editable working-set chips (add via inline type-ahead, remove via ×), count, and the
**Excel 다운로드** button.

### ② Parameter selection layer
- Parameter **search box** (e.g. type `WAFER`).
- **Coverage filter chips:** 전체 / **공통** (exists in every selected recipe) / 부분 / 고유.
- **Overlap grid** (parameters × recipes) with a **checkbox** per parameter row and a
  coverage tag (`ALL`, `3/4`, …). Cells show ✓ / — for presence.
- **공통 전체 선택** quick action — selects every parameter shared by all recipes (the
  "I already know WAFER is in all of them" path).
- Checked parameters flow into the comparison output as tabs.

### ③ Comparison output
- **View toggle:** 나란히 (side-by-side matrix) ⇄ 분포 (grouping/outlier). Default is
  나란히 for small N, 분포 once `count > GROUPING_DEFAULT_THRESHOLD`; user can switch
  freely. Both render from the same fetched dataset.
- **Parameter tabs:** one tab per checked parameter; one parameter's comparison shown
  at a time.
- **차이만 보기** toggle: hides rows where every recipe agrees.

**나란히 (matrix):** rows = attributes, columns = recipes.
- IDP block (per-parameter fields: Addressing, Mother_Para, Region, Meas_Counting,
  dnumber_removed, …). Recipes missing the parameter show `없음`/`—`.
- AMP block with **slot tabs** (Add 1/2/3 · Meas 1/2). The selected slot shows a
  **thumbnail row** (one image per recipe, click → lightbox) above its field rows
  (Mag, Vacc, I_probe, Frame, Scan, WD, Det, and role-specific fields like
  Template/MatchScore for address or Algo/ROI/EdgeThr for measure).
- Differing cells highlighted. Sticky parameter/attribute column; columns horizontally
  scroll with **column virtualization** for large N.

**분포 (grouping/outlier):** for the active parameter + slot, each field row collapses
the N recipes into **value buckets** — e.g. `Mag: 50.0K ×62 · 80.0K ×31 · 100.0K ×7 ⚠`.
Minority/outlier buckets are flagged; clicking a bucket lists the recipes holding that
value. Answers "which recipes are configured differently?" without horizontal scrolling.

## 6. Data & Backend

### Batch compare endpoint (new)
- **Route:** `POST /<tool_slug>/recipe-search/compare`
- **Body:** `{ "fab_name": "R3", "recipe_names": ["…", "…", …] }`
- **Response:** one compact object per recipe containing only comparison-relevant data:

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
          "idp": { "Addressing": "Yes", "Mother_Para": "Para_2", "Region": 5, ... },
          "amp": [ { "slot": "img_meas1", "role": "measure", "Mag": "50.0K", ... }, ... ]
        }
      ]
    }
  ]
}
```

- Drops `wafer_mp_info`, `wafer_align_info`, `align_images` (never shown in comparison),
  cutting per-recipe payload to ~5–15 KB → ~1 MB for 100 recipes in a single request.
- **Data layer:** add `get_recipe_compare_data(tool_type, fab_name, recipe_names)` to
  `recipe_search/data.py`, reusing the existing seeded `generate_idp_image_info` /
  `generate_amp_info` so a recipe's compare payload matches its open payload. Routes
  import from `.data` only (home↔office swap stays isolated).

### Frontend fetching
- **Composable:** `useRecipeCompareApi.fetchCompare({ toolType, fabName, recipeNames })`
  → POSTs the batch endpoint. In-flight dedup keyed on the sorted name list, matching
  the existing `useRecipeSearchApi` pattern.
- Compare page wraps it in `useAsyncData` with a cache key over `(toolType, fab, sorted
  names)`.

### Client-side derivations (no server compute)
- **Overlap + coverage** (which parameters in which recipes, ALL/partial/unique).
- **Diff detection** per attribute row.
- **Value grouping** for 분포 view.
- **Excel workbook** (SheetJS): sheet `Overlap` (parameters × recipes presence) + one
  sheet per slot (`Meas 1`, `Add 1`, …) of attributes × recipes for the selected
  parameters, + a `Recipes` meta sheet. Generated from the already-loaded payload.

## 7. Components (new, under `components/ebeam/recipeCompare/`)

Following the folder-prefix auto-import convention (`recipeCompare/Foo.vue` →
`<EbeamRecipeCompareFoo>`), and reusing `recipeOpen/ImgThumb.vue` +
`recipeOpen/ImageLightbox.vue` for images.

| Component | Responsibility |
| --- | --- |
| `RecipeCompareView.vue` | Page shell; fetch, layout the three layers, view-mode state |
| `recipeCompare/RecipeSetBar.vue` | Working-set chips, inline add, Excel button |
| `recipeCompare/ParameterSelector.vue` | Search + coverage filters + overlap grid + checkboxes |
| `recipeCompare/CompareMatrix.vue` | 나란히 view: IDP block + slot tabs + thumbnail row + diff cells |
| `recipeCompare/CompareGrouping.vue` | 분포 view: value buckets + outlier flags + recipe drill |
| `recipeCompare/SearchSelectTray.vue` | Sticky tray on the search page |

Plus:
- `pages/ebeam/cd-sem/[fab]/recipe-search/compare.vue` and the `hv-sem` twin — thin
  wrappers passing `tool-type`/`tool-label`, matching the existing leaves.
- `composables/useRecipeSelectionSet.ts`, `composables/useRecipeCompareApi.ts`.
- `utils/recipeCompare.ts` — overlap, coverage, diff, grouping, and Excel-build pure
  functions (unit-testable, no Vue).

## 8. Out of Scope (this pass)

- Recipe switcher inside open/lateral/meas-hist (fast-follow; the set composable is
  built switcher-ready).
- Cross-fab or cross-tool comparison.
- Server-side Excel generation.
- Comparing `wafer_mp_info` / alignment data.

## 9. Testing

- **Pure functions** (`utils/recipeCompare.ts`): overlap/coverage classification, diff
  detection, value grouping + outlier flagging, Excel workbook shape — unit tests.
- **Working set composable:** accumulation across query changes, per-scope isolation,
  localStorage persistence round-trip.
- **Backend:** `get_recipe_compare_data` returns one entry per requested recipe, matches
  the corresponding open payload's parameters, omits the dropped tables.
- **Manual/Playwright:** check → search again → check persists → 비교하기 → 공통 전체
  선택 → slot tabs → 차이만 → 분포 toggle → Excel download.
