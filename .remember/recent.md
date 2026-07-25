# Recent

```

# Recent

## 2026-07-24
MSR image tool-FTP fetch shipped (360+ tests, MinIO 72h cache, FTP IPv4 guards, multi-backend support), BM/PM office adapter built (57-58 tests, fab_inform_notes/tool_maintenance_plan datatables, office_example.py), Bento deck delivered (15 slides, Vue→TS+Nuxt conversion, 60+ color remaps). Fixed critical bugs: PPID silent-drop (model_to_tool_type prefix-matching), meas-hist >100% ratio (fail_ratio normalization refactored), chart zoom point-click (notMerge state loss), beam-trend zoom (withPreservedZoom). Extended features: msr_image TIFF adapter + wafer geometry nm-scale, radar axis-range control (reso_eb 7.5–8.5, noise 5.7–6.7, cross-tab-persisted), field-location CD pairing (chip_coordinate join design). Infrastructure: diagnosed skewvoir search bug (search_all missing from OpenSearch), designed field-location Spec 1&2 with geom mapping, specified deploy packer (Python allowlist + preflight, 7 TDD tasks).

## 2026-07-23
Live-alarm broadcast: specification→implementation complete (35 files, 1926 LOC, 746 tests passing), Redis ZSET backend with APScheduler writer (15s poll), incorporated Codex review (11 issues), executed via 9-task SDD. Chat LLM: HCP gateway integration (3 models), environment-driven configuration, E2E verified, MIGRATION.md documented. UI improvements: LaserPower 3-view (raw/pct/scatter), RecipeSearchView spacing, RecipeMeasHistView sorting, SharpnessPanel timestamp→ID, FeatureTabs label removal, AnnouncementBanner viewport fix. Infrastructure: BM/PM adapter built (6 SDD tasks), msr_image fetch designed (MinIO cache, IPv4 validation), fdc_key casing bug fixed (7 files).

## 2026-07-22
Office provider adapters completed: recipe_search + fail_issue + lateral_recipe on Redis v3 and OpenSearch. Hardware providers split into 7 per-tab directories (FDC, sharpness, BSM, MDC, reso_center, mdc, sce) with office/mock fallback pattern; fixed critical bugs (redis hang, timezone normalization UTC→KST, MinIO paths, msr_file retrieval). UI improvements: recipe-search tokenized matching, cascade filters (+9 tests), scrollable chip strip; presence-detection wired; 188 BE + 485 FE tests.

## Identity Candidates
- IDENTITY CANDIDATE: Spec-driven sub-project sequencing with TDD + comprehensive testing (AFM A–D roadmap, Chat feature paired with dashboard polish)