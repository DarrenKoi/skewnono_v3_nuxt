# 01 — Extract the HV-SEM variant chip bar

**What to build:** the multi-image variant chip bar (about 18 lines of button markup plus the index ref and the reset-on-change watch) is copied near-verbatim into three skewvoir components — `dashboard/SemImage.vue`, `gallery/ImageViewer.vue`, `position/SiteEvidenceDrawer.vue` — and the copies are already drifting (`selectedIndex` vs `variantIndex`). Extract one `VariantChips.vue` component and consume it from all three, preserving each context's reset behavior.

**Why:** review Standards axis, worst finding of the HV-SEM group (Duplicated Code). Interactive markup with local state is the most expensive thing to triplicate — behavior fixes (keyboard, focus, reset timing) must be repeated three times or silently diverge. The divergence has already started: the copies disagree on the index name (`selectedIndex` vs `variantIndex`) one day after landing.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 6ce0d453 — EbeamSkewvoirVariantChips, selectedIndex→variantIndex 통일

- [ ] One `VariantChips` component is consumed by all three call sites; the copies are deleted
- [ ] Selected-variant reset on image-list change behaves identically in dashboard, gallery, and drawer
- [ ] No visual or aria change (chips keep `aria-pressed` semantics)
