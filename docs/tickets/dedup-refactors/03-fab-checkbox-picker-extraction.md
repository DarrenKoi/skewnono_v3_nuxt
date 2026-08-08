# 03 — Extract the checkbox multi-select picker pattern

**What to build:** the checkbox `#item-leading` slot with the hidden trailing icon is now a third copy — `CompareToolPicker.vue`, `ScePanel.vue`, and the landing page's FAB dropdown (`pages/index.vue`, whose commit comment even says "same pattern as hardware/CompareToolPicker"). Three copies is the extract threshold: pull the pattern into one shared component and consume it in all three places.

**Why:** review Standards axis, judgement call (Duplicated Code). Three copies is this codebase's de-facto extract threshold, and the landing-page copy's own commit comment cites the pattern source — the duplication is acknowledged intent, not accident. Checkbox pickers carry selection-state edge cases (indeterminate, disabled rows); three homes means three places to fix the next edge case.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — c7d6fbb5 — AppSelectCheck (ScePanel 의 text-white 드리프트도 함께 해소)

- [ ] One shared multi-select picker component replaces the three copies
- [ ] Landing FAB multi-select, hardware compare picker, and ScePanel all behave as before (visual check)
- [ ] Selection state flow still goes through the existing stores/composables unchanged
