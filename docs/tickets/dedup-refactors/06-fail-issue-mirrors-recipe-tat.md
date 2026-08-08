# 06 — Fail-issue mirrors of the recipe_tat twins: forked landmine comment, small shared helpers

**What to build:** the two new fail-issue components copy ~600 lines from their recipe_tat twins — `sortingOptions` with its `manualSorting` rationale comment, `getSortIcon`, `toggle`, `filteredRows`, `colorByEqpId`, `cacheKey`, `tableUi` — and `props.section === 'align' ? … : …` recurs 6× in the fleet table and 5× in the compare panel. Spec §10 deliberately deferred merging the two fleet tables until a third consumer exists, so the component-scale merge stays **out of scope**. In scope here: (1) the `manualSorting` landmine comment is now maintained in two files — the exact drift that comment exists to warn about — so cross-reference both copies ("if you edit this, edit the twin") or hoist it to one canonical home; (2) the `at()` percentile accessor and the `편중` narrow clause (`recipe_count <= p10 && top_recipe_share >= SHARE_CEIL`) are now duplicated between `failEquipmentSignals.ts` and `equipmentSignals.ts` — `SHARE_CEIL` already crosses that boundary, so the helpers can follow it into one home; (3) optionally collapse each component's section ternaries into one aspect-keyed accessor map. Note for dedup-refactors/05: fail_issue's `EquipmentGridRow` is a second positional grid tuple (a 7-tuple) threaded mock → shape → office — extend that ticket's NamedTuple conversion to it when it runs.

**Why:** review Standards axis, judgement calls (Duplicated Code ×2, Repeated Switches), bounded by spec §10's explicit deferral of the big merge. The small items are the ones that drift silently: a forked cautionary comment stops being true in one file first, and the `at()` / narrow pair are identical predicates that can diverge one boundary condition at a time — the narrow clause's inclusive `<=` is already load-bearing (nearest-rank p10).

**Blocked by:** None — can start immediately. dedup-refactors/05's tuple item should absorb the fail_issue twin but does not block this.

**Status:** done (2026-08-09) — f59d5333 — isNarrowMix/percentileAt 공유, MANUAL_SORTING_OPTIONS 단일 출처. 컴포넌트 병합은 spec §10 대로 미시도

- [ ] The `manualSorting` rationale comment is cross-referenced or single-sourced across both fleet tables
- [ ] `at()` and the `편중` narrow clause have one home (next to `SHARE_CEIL`), consumed by both signal modules; boundary behavior (`<=`) unchanged
- [ ] Component-scale merge explicitly NOT attempted — spec §10's deferral stands
- [ ] Frontend suites green (`npm test`, `npm run typecheck`)
