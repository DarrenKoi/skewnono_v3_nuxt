# 03 — Time-Series lens tabs use the shared pill role class

**What to build:** the lens tabs in skewvoir's `views/TimeSeries.vue` restate the navigation pill's geometry with ad-hoc utilities (`h-11 px-5 text-[15px] rounded-(--sk-r-nav) border-(--sk-ink) bg-(--sk-ink)`), because `SkNavPill` was rejected for aria reasons — a sound rejection, but the geometry is now a second copy that drifts silently on any pill retone. Move the shared geometry into a role class (sibling to the dark-chip rule extracted in design-tokens/01) and have the lens tabs consume it while keeping their own aria semantics.

**Why:** review Standards axis, judgement call (Duplicated Code). Rejecting `SkNavPill` for aria reasons was sound, but copying its geometry into utilities recreates the dependency invisibly: a pill retone changes `SkNavPill` and the role classes, while these tabs quietly keep the old look. DESIGN.md's role-class section deprecates ad-hoc `text-[15px]`-style sizing for exactly this reason.

**Blocked by:** 01 — Chip dark override consumes the `--sk-ink-fg` token (the shared role-class home lands there).

**Status:** done (2026-08-09) — ba4926c9 — sk-nav-pill 지오메트리를 main.css role 클래스로 승격, lens 탭이 소비

- [ ] Lens tabs reference the shared role class instead of restating pill geometry in utilities
- [ ] The ad-hoc `text-[15px]`-style sizing is gone from the tab markup
- [ ] Tab appearance and aria behavior unchanged (visual check)
