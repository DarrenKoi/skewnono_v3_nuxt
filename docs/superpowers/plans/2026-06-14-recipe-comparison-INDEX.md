# Recipe Comparison Service — Implementation Plans (index)

Design spec: `docs/superpowers/specs/2026-06-14-recipe-comparison-design.md`.

Compare many recipes (target ~100) within one `(toolType, fab)`. Overlap grid →
parameter drill-down (slot tabs + image thumbnails), with a 나란히 (side-by-side
matrix) ⇄ 분포 (grouping/outlier) view toggle, seeded from a persistent multi-select
working set on the search page, exportable to Excel client-side.

## Execute in order

1. **[Plan 1 — Data + Logic Foundation](2026-06-14-recipe-comparison-plan1-data-foundation.md)**
   Backend batch `compare` endpoint + `get_recipe_compare_data`; `useRecipeCompareApi`
   composable; pure `utils/recipeCompare.ts` (overlap/coverage, diff, value-grouping,
   workbook builder) with full tests. **No UI.** Prerequisite for 2 & 3.
2. **[Plan 2 — Selection Layer](2026-06-14-recipe-comparison-plan2-selection-layer.md)**
   `useRecipeSelectionSet` working-set composable (mirrors `useRecipeRecentSearches`) +
   checkbox column + sticky `SearchSelectTray` on the existing search page.
3. **[Plan 3 — Compare View](2026-06-14-recipe-comparison-plan3-compare-view.md)**
   `compare.vue` page wrappers + `RecipeCompareView` shell + `ParameterSelector` +
   `CompareMatrix` (나란히) + `CompareGrouping` (분포) + Excel download + Playwright check.

## ⚠️ Confirm before coding (key decisions, from the spec)

- **Scope = one `(toolType, fab)`.** No cross-fab/cross-tool comparison. Working set is
  scoped per `(toolType, fab)` like recent searches.
- **State-authoritative, not URL.** Compare page reads the working-set composable; the
  recipe list is NOT round-tripped through the URL (100-name URLs are impractical).
- **First pass:** only 비교하기 consumes the full set. Tray 열어보기/횡전개/측정이력 open
  the **first** selected recipe (existing single-recipe behavior). In-page recipe
  switcher across those three views is a documented fast-follow, NOT in these plans.
- **Excel = client-side** (`xlsx`/SheetJS, dynamic import). The workbook *shape* is built
  by a pure, tested function; only the file write touches the library.
- **Outlier rule:** a value bucket is an outlier when it is not the single largest
  bucket AND its share `≤ 0.25` (`OUTLIER_SHARE`). Default to 분포 view when recipe
  count `> 8` (`GROUPING_DEFAULT_THRESHOLD`).

## Pre-flight (each task is TDD where pure logic exists)

- Frontend tests: `cd front-dev-home && npm run test` (`node --test "app/**/*.test.ts"`).
  Typecheck: `npm run typecheck`. Lint: `npm run lint`.
- Backend: no pytest — verify via `python -c` / `curl` against Flask (:5050).
- New dependency (Plan 3): `cd front-dev-home && npm i xlsx`.
- Use **superpowers:subagent-driven-development** or **superpowers:executing-plans** to
  run a plan.
