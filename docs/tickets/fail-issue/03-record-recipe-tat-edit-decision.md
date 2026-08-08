# 03 — Decide: recipe-tat files were edited against spec §10's read-only fence

**What to build:** a decision, then alignment. Spec §10 fences the Recipe TAT equipment view as read-only for this work ("`Recipe TAT` 탭의 장비별 뷰 수정. 이 작업은 그 코드를 읽기만 합니다"), yet commits bc1732c5 / f1e2c3832 edited `useRecipeTatApi.ts` (removed its `MAX_COMPARE_EQPS`) and `RecipeTatEquipmentView.vue` (import switch) and created `utils/analyticsLimits.ts` — to kill a real Nuxt auto-import collision on `MAX_COMPARE_EQPS`. The change is behavior-preserving and the motivation is genuine, but it is unsanctioned. Either amend the spec (a short §10 note recording the exception and why the collision forced it) or revert to per-file constants under names that cannot collide. Deliverable is the recorded decision plus code and spec agreeing.

**Why:** review Spec axis, scope creep — same shape as recipe-tat/01. The fence exists so a reviewer can trust "recipe-tat untouched" when assessing regression risk; an unrecorded exception means the next session reads §10 as true when it no longer is. Note the collision is already fixed either way — this ticket is about the record, not the code behavior.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — ba99784b — 유지, spec §10.1 에 예외 기록

- [ ] Decision recorded in the spec next to §10 (exception + reason), or the edits are reverted
- [ ] If kept: `analyticsLimits.ts` carries a header comment noting why a shared module beat the fence
- [ ] Frontend suites stay green (`npm test`, `npm run typecheck`)
