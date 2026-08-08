# 04 — Fail-issue tables inherit their siblings' DESIGN.md violations

**What to build:** the two new fail-issue components byte-copied the recipe_tat twins' token drift, so everything design-tokens/02 flags now has a second home. `FailIssueFleetTable.vue` ships the zinc count chip (`bg-zinc-100` / `text-zinc-600` / `dark:` variants) at `text-[10px]` with `rounded` (4px), and its signal badges repeat `text-[10px]` + `rounded`; `FailIssueEquipmentCompare.vue`'s selection chip renders data values (eqp_id, counts) at `text-[11px]` with `rounded-md`. Three documented-rule breaks: zinc-on-chrome (DESIGN.md §Don't — zinc survives only in table hovers and the empty-state message), sub-12px data values (§Typography — "a data value never renders below 12px"), off-scale radii (§Shapes — soft rectangles on the 6/8/10/14 scale only, hand-written markup uses `var(--sk-r-*)`). Fix together with design-tokens/02 so both tab families land on the same tokens / role classes in one sweep.

**Why:** review Standards axis, hard violations of DESIGN.md, inherited verbatim from siblings already flagged in design-tokens/02. DESIGN.md's Known Gaps classifies these classes as deletions-in-progress — every new copy doubles the edit surface of the eventual fix and reads as fresh precedent for the next table.

**Blocked by:** None — can start immediately. Strongly prefer landing with design-tokens/02.

**Status:** done (2026-08-09) — 8469edca — 02 와 한 sweep 으로 착지

- [ ] No zinc utilities, no sub-12px data values, no off-scale radii in `FailIssueFleetTable.vue` / `FailIssueEquipmentCompare.vue`
- [ ] Fix uses the same tokens / role classes chosen for design-tokens/02 — one sweep, both families
- [ ] Light and dark appearance verified in both fail-issue tabs (Align Fail / Meas Fail 장비별 모드)
