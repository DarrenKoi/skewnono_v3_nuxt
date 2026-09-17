# Brief A — 스큐보아 deep-link seam + 장비 리스트 button

Worktree: /Users/daeyoung/Codes/skewnono-skewvoir-links (branch work/skewvoir-links). Work ONLY there. Frontend at `frontend/`. Another agent (Brief B) edits other files in the same worktree at the same time — touch only the files listed here, do not run git commands, do not format unrelated files.

Already written for you (read first): `frontend/app/utils/skewvoirLinks.ts` — `skewvoirSearchRoute(toolType, {eq, recipe, fab})` builds `/ebeam/<tool>/skewvoir?q=eq:X recipe:Y&fab=R3`, and `hasSkewvoir(toolType)`.

## Task 1 — SearchLanding applies the URL once
File: `frontend/app/components/ebeam/skewvoir/SearchLanding.vue` (search state comes from `useMeasHistSearch`, see `frontend/app/composables/useMeasHistSearch.ts`).

On arrival with `route.query.q` (string) and/or `route.query.fab`:
1. set `search.queryText.value = q`
2. if `fab` present, set `search.filters.value = { ...search.filters.value, fab: [fab.toUpperCase()] }` (filters.fab is `string[]`; check the persisted default with `emptyMeasHistFilters`)
3. call `search.search()` as soon as `search.searchDisabled.value` is false (facets may still be loading on a cold load — use a `watch(..., { immediate: true })` that fires once, then stops)
4. `router.replace({ path: route.path })` to drop `q`/`fab` from the URL after applying, so a later reload/back does not clobber what the user typed afterwards.

Keep it to ~15 lines inside SearchLanding's script; no new composable. Use `qstr` from `~/utils/skewvoirAnalysis/routeQuery` for reading query values.

## Task 2 — 장비 리스트 button
File: `frontend/app/components/ebeam/ToolInventoryView.vue`, the `#eqp_id-cell` slot (currently: eqp_id + "H/W 상태" UButton). Add a second UButton right after it, same size/color/variant, `trailing-icon="i-lucide-arrow-right"`, label `스큐보아`, aria-label `` `${row.original.eqp_id} 스큐보아 검색 열기` ``, only when `hasSkewvoir(toolType)`; `:to="skewvoirSearchRoute(props.toolType, { eq: row.original.eqp_id, fab: row.original.fab_name })"`. Navigates in the same tab (like H/W 상태).

## Verify (from `frontend/`)
- `npm run typecheck` and `npm run lint -- app/components/ebeam/skewvoir/SearchLanding.vue app/components/ebeam/ToolInventoryView.vue` clean.
- Manual: Flask must be on :5050 and Nuxt on :3000 (start Flask with `.venv/bin/python index.py` from the MAIN repo /Users/daeyoung/Codes/skewnono_v3_nuxt if not running; run Nuxt from THIS worktree's frontend with `npm run dev` only if :3000 is free — otherwise just report that the browser check was skipped). Then open `http://localhost:3000/ebeam/cd-sem/skewvoir?q=eq:<some eqp_id from /api/sem-list>&fab=R3` with cookie LASTUSER=local-dev and confirm the 검색 결과 table shows only that tool.

Report: files changed, what you verified, anything you were unsure about. Keep the diff minimal — no refactors.
