# 02 — Share the `?preview` flag predicate

**What to build:** the `?preview` query predicate currently exists twice — `_wants_preview()` in `msr_image/routes.py` and an inlined identical expression in `recipe_search/routes.py`. Keep one conservative allowlist parser (`1` / `true` / `yes`; unknown or missing values serve the original) next to `to_preview` in `msr_image/preview.py`, and call it from both route modules.

**Why:** review Standards axis, hard violation (Duplicated Code on a parsing rule). The predicate is a conservative allowlist — the kind of rule that gets tightened or loosened deliberately later — and two copies drift independently: a future change to one route silently leaves the other route parsing `?preview` differently. `recipe_search` already imports `to_preview` from `msr_image.preview`, so the shared home already exists.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 8c4df345 — preview.py 의 wants_preview() 공유, 라우트 커버리지 추가

- [ ] A single shared predicate is imported by both `msr_image` and `recipe_search` routes; the inline copy is gone
- [ ] Unknown or missing `preview` values still serve the original bytes (no behavior change)
- [ ] Existing preview tests pass; add route-level coverage for the flag on the recipe-search image path
