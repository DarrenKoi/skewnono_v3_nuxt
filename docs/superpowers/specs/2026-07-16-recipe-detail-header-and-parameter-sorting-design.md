# Recipe Detail Header and Parameter Sorting — Design

- Date: 2026-07-16
- Status: Approved — implementation plan written
- Area: `front-dev-home` E-beam Recipe detail screens

## Goal

Make the Recipe detail pages consistent with the compact header used by pages
such as `recipe-status`, remove redundant equipment/Fab identity, make the
back action easier to find, provide direct navigation among the three Recipe
detail screens, and make the parameter table sortable.

## Header

Replace the custom `RecipeOpenView` title/stat layout with `EbeamMetaBar`.

- The Recipe name is the title.
- The detail timestamp is the subtitle when detail data is available.
- Do not render `CD-SEM · R3`, `HV-CD-SEM · R3`, or equivalent tool/Fab
  identity anywhere in the `open` page header.
- Remove the duplicate response metadata line (`fac_id · tool_category`) and
  the standalone right-side statistics card.
- Keep `EbeamRecipeSwitcher` above the header when a multi-Recipe work set is
  active; it does not repeat tool/Fab identity.

The existing missing-query, loading, error, and loaded-content states remain
unchanged apart from their position beneath the new header.

Apply the same identity-removal rule to the `횡전개` and `측정 이력` detail
headers. Remove their tool/Fab eyebrow strings, including suffixes such as
`· 횡전개` or `· 측정 이력`; keep the Recipe title, existing explanatory
subtitle, and summary values. This requirement applies to all three Recipe
detail screens, not to unrelated E-beam pages.

## Detail Navigation

Add one compact Recipe-detail navigation group beside the back button:

1. `돌아가기` — a larger `md` button that preserves the existing history-back
   behavior and Recipe-search fallback route.
2. `열어 보기`
3. `횡전개`
4. `측정 이력`

The three detail destinations use the existing `RECIPE_ROW_ACTIONS` and
`recipeDetailRoute` definitions so labels, icons, and paths continue to have
one source of truth. The active destination is visually selected and exposed
with `aria-current="page"`; selecting the active destination does nothing.

Use the same navigation group on `RecipeOpenView`, `RecipeLateralView`, and
`RecipeMeasHistView`. This keeps the switching controls available after each
hop instead of only on the initial `open` screen. Each hop preserves the
current `recipe_name` and the optional `set=1` query used by the work-set
switcher. It must not add a new Recipe query or change API requests.

## Parameter Table Summary

Move the Recipe-wide summary values into the `파라미터 목록` table header:

- `측정 포인트`: `wafer_mp_info.length`
- `Align 포인트`: `wafer_align_info.length`

Render them as compact inline label/value items next to `파라미터 목록 · N`,
following the existing Recipe Status inline-summary treatment. Keep the
`Align 정보` action in the same table-header area. Do not add these totals as
row columns because they describe the whole Recipe, not individual
parameters. Do not repeat `Image 정의`; the existing `파라미터 목록 · N` count
already represents the IDP parameter rows.

## Parameter Table Sorting

Every visible data column is sortable:

- Parameter
- SEQ
- Region
- Addressing
- Mother
- Double
- Cnt
- d#_rm

Initial state is `SEQ` ascending. Clicking the active header toggles ascending
and descending. Clicking a different header selects it in ascending order.
Headers show the existing up/down/unsorted Lucide indicators and use
`aria-sort` for assistive technology.

Sort numbers numerically, booleans by false/true, and text with numeric-aware
locale comparison. `SEQ` sorts by the underlying `SEQ` value even though the
cell displays `SEQ/Last_SEQ`. Equal values retain source order for stable,
predictable results.

Sorting must not break the selected row. The table keeps each displayed row's
source index, highlights selection against that source index, and emits the
source index on click so the right-side image/AMP/overview content continues
to show the clicked parameter.

## Implementation Boundaries

- Add a small shared Recipe-detail navigation component for the three detail
  screens.
- Add a pure Recipe-open sorting utility and focused Node tests before wiring
  it into `recipeOpen/IdpTable.vue`.
- Extend `IdpTable` props with the two Recipe-wide summary counts.
- Update only the relevant Nuxt frontend files; backend endpoints and response
  shapes remain unchanged.
- Preserve unrelated worktree changes.

## Verification

- Focused sorting tests cover default SEQ ascending order, text and boolean
  ordering, direction toggling inputs, stable ties, and source-index mapping.
- Run the complete frontend Node test suite.
- Run frontend ESLint and Nuxt type checking.
- Run `git diff --check`.
- Inspect the final diff to confirm no `CD-SEM · R3`-style identity remains in
  any of the three detail headers, summary values appear in the table header,
  navigation is present on all three detail screens, and SEQ ascending is the
  initial sort.
