# 03 — Preview route cleanups

**What to build:** four small cleanups around the TIFF preview path. First, a bytes-level preview helper so `recipe_search/routes.py` stops constructing a placeholder `FetchedImage(payload, content_type, None)` just to discard a field. Second, a named preview-options type replacing the three anonymous inline `{ preview?: boolean }` copies across `useMsrImageApi` and `useRecipeParamDetail`. Third, `Content-Disposition` on preview responses should not name WebP bytes with a `.tif` filename (cosmetic; `inline` stays). Fourth, the `msr_image` mock docstring still references the frontend TIFF download-fallback path that this branch removed — bring the docstring back in sync.

**Why:** review Standards axis, judgement calls bundled because they share one neighborhood. Constructing a contract object with a placeholder `None` and discarding a field misuses the `FetchedImage` type to reach a bytes transform (Middle Man); three anonymous inline option types drift apart; a `.tif` filename over WebP bytes misleads anyone who saves the response directly; and a docstring describing a removed fallback path actively teaches the next session wrong — in this repo, mock docstrings are how office knowledge survives.

**Blocked by:** 02 — Share the `?preview` flag predicate (the helper lands beside that predicate).

**Status:** done (2026-08-09) — 8c4df345 — preview_bytes() 로 FetchedImage 자리표시자 제거, ImagePreviewOptions 명명, Content-Disposition 은 변환된 경우에만 확장자 교정. mock docstring 항목은 tiff-preview/01 이 폴백을 되살려 이미 참이 됨

- [ ] `recipe_search` calls a bytes-level helper; no placeholder contract object is built and discarded
- [ ] One named preview-options type is shared by the three frontend call sites
- [ ] Preview responses carry a filename/extension consistent with the converted bytes, or none
- [ ] The `msr_image` mock docstring no longer describes a removed frontend fallback path
