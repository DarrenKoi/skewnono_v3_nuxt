# 01 — promoteRecipeSelectionsToRedis matches (recipe, fab) pair-exactly

**What to build:** `promoteRecipeSelectionsToRedis` currently matches catalog rows by bare recipe name and adopts the first matching row's fab, overwriting the entry's own fab. With the cross-fab recipe-name overlap documented in the multi-fab Phase B spec (R3 ∩ M16B ≈ 20%), a promoted OpenSearch selection can be silently rerouted: the compare body and `&fab_name=` owner-fab routing then hit the wrong fab's registry. Selection identity is the (recipe_name, fab_name) pair per spec §5, so promotion must require a pair-exact catalog hit. Only entries whose fab is unknown (`''`) may use a name-only lookup — and a non-unique name must not guess; keep the entry's own fab instead.

**Why:** flagged as the worst finding on *both* review axes. Spec axis: §5 defines selection identity as the (recipe_name, fab_name) pair, and this function rewrites that identity by name-only matching. Standards axis: first-row-wins adoption is a silent correctness defect — no error, no log, the user just sees the wrong fab's detail/compare data. The ~20% cross-fab name overlap documented in the Phase B spec makes this a live risk, not a corner case.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 4f086261 — 회귀 테스트 4건

- [ ] Promotion requires a (recipe_name, fab_name)-exact catalog hit when the entry already carries a fab
- [ ] Name-only fallback applies only to fab-unknown entries, and only when the name maps to exactly one fab
- [ ] A recipe name present on two fabs never has its entry's fab rewritten to the first catalog row
- [ ] Regression test: two fabs sharing one recipe name promote to their own fabs
