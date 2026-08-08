# 02 — Fab-identity hygiene

**What to build:** three small correctness items around fab identity. First, `useRecipeSelectionSet.has` and `RecipeSwitcher.isActive` compare backend-supplied fab names with raw `===`; `utils/fab.ts` mandates `sameFab` for exactly this. Second, `fetchCompare` no longer trims recipe names before POST (the old code did), so padded names go out verbatim. Third, `useLiveAlarmFeed` joins the fab list once, non-reactively — correct today only because pages remount via `definePageMeta({ key: fullPath })`; make the join reactive (or key the feed) so the trap stops being latent.

**Why:** review Standards axis, three judgement calls that share one root — fab/name identity handling that is correct today only by accident of upstream normalization. Raw `===` bypasses the invariant `utils/fab.ts`'s docstring explicitly mandates; the dropped trim is a wire-behavior regression introduced during the multi-fab rework; and the non-reactive fab join works only because pages happen to remount on route-key change — remove that remount (an unrelated optimization could) and the feed silently listens to stale fabs.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 6b811ca4 — live-alarm 은 반응형 대신 뷰 :key (useState 키는 반응형 불가)

- [ ] Fab-name equality goes through `sameFab` at both call sites
- [ ] Recipe names are trimmed before the compare POST, as before the regression
- [ ] `useLiveAlarmFeed` reacts to fab-list changes without relying on page remount
