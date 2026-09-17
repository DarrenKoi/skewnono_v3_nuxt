# Brief B — 스큐보아 buttons in Recipe 현황 / Recipe 검색 / 디바이스 통계 lot popup

Worktree: /Users/daeyoung/Codes/skewnono-skewvoir-links (branch work/skewvoir-links). Work ONLY there. Frontend at `frontend/`. Another agent (Brief A) edits `SearchLanding.vue` and `ToolInventoryView.vue` in the same worktree — do not touch those, do not run git commands, do not format unrelated files.

Already written for you (read first): `frontend/app/utils/skewvoirLinks.ts` — `skewvoirSearchRoute(toolType, {eq, recipe, fab})` returns a `{path, query}` route to 스큐보아's search page that will run the search on arrival (Brief A wires that), and `hasSkewvoir(toolType)` (true only for `cd-sem` / `hv-sem`).

Recipe identity rule (read the doc comment on `recipeDetailId` in `frontend/app/utils/recipeView.ts`): 스큐보아 must receive the class-qualified `full_name`, the same id the 측정 이력 screen receives. Use `recipeDetailId(row)` wherever the row has `recipe_name`/`full_name`.

## Task 1 — Recipe 현황 (both tabs)
File: `frontend/app/components/ebeam/RecipeRowActions.vue` (used by RecipeTatView + FailIssueView, which are what Recipe 현황 renders). Add a 4th icon button after the three `RECIPE_ROW_ACTIONS`: icon `i-lucide-telescope`, label/tooltip `스큐보아`, same size/variant/class, same multi-fab behaviour (dropdown per fab when `multiFab`, direct when single). Route: `skewvoirSearchRoute(props.toolType, { recipe: detailId.value, fab: ownerFab })`; render only when `hasSkewvoir(props.toolType)`. Do NOT add it to `RECIPE_ROW_ACTIONS` — that array types `screen: RecipeDetailScreen` and feeds the detail-page nav too.

## Task 2 — Recipe 검색
File: `frontend/app/components/ebeam/RecipeSearchView.vue`, the `#open-cell` slot (열어 보기 / 횡전개 / 측정 이력 UButtons around line 910). Add a 4th UButton after 측정 이력: `icon="i-lucide-telescope"`, `label="스큐보아"`, same size/color/variant, `:to="skewvoirSearchRoute(props.toolType, { recipe: row.original.recipe_name, fab: row.original.fab_name })"` (recipe-search rows' `recipe_name` IS already the qualified name — see the same doc comment). Guard with `hasSkewvoir(props.toolType)` if `props.toolType` can be a non-SEM family; check its type.

## Task 3 — 디바이스 통계 lot popup
Files: `frontend/app/components/cdsem/comparison/LotDetailModal.vue` and its per-recipe card `frontend/app/components/cdsem/comparison/StepOutlierCard.vue` (rows are `RecipeInfoRow` from `useRecipeStatisticsApi.ts`: `recipe_id`, `fac_id`, `eqp_id`, …). Device statistics is cd-sem only; `fac_id` IS the fab name here (`R3`, `M16` … — the page compares it with `sameFab(row.fac_id, 'R3')`).

On each recipe card add a compact icon row (xs ghost UButtons with UTooltip, like RecipeRowActions) with four links that open in a NEW TAB (`target="_blank"` on the UButton with `:to=`): 열어 보기, 횡전개, 측정 이력 via `recipeDetailRoute('cd-sem', fac_id.toLowerCase(), screen, recipeId, 'redis', fac_id)` (icons from `RECIPE_ROW_ACTIONS`), and 스큐보아 via `skewvoirSearchRoute('cd-sem', { recipe: recipeId, fab: fac_id })` with `i-lucide-telescope`. `recipeId`: check the shape of `recipe_id` in `backend/ebeam/device_statistics/providers/mock.py` and `docs/datatables/` — if it is already `CLASS/NAME`-qualified use it as is; if it is bare, say so in your report and still wire the links (측정 이력 and 스큐보아 accept either). Stop the click from toggling the card's expand (`@click.stop`). Put the row where it reads naturally next to the `recipe_id` value; keep DESIGN.md tokens (`--sk-*`), no inline hex.

## Verify (from `frontend/`)
- `npm run typecheck`; `npm run lint -- <the files you touched>` clean; `npm test` still green.
- Manual if :3000 is already serving this worktree (do not start a second dev server if the port is taken; if nothing is on :3000 you may `npm run dev` from this worktree's frontend, Flask lives on :5050 and is started from the MAIN repo `/Users/daeyoung/Codes/skewnono_v3_nuxt` with `.venv/bin/python index.py`): cookie `LASTUSER=local-dev`; check `/ebeam/cd-sem/r3/recipe-status`, `/ebeam/cd-sem/r3/recipe-search`, and the lot popup at `/ebeam/cd-sem/device-statistics/comparison`. Report what you could and could not check.

Report: files changed, what you verified, anything you were unsure about. Minimal diff, no refactors.
