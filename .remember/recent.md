# Recent

## 2026-07-28
Completed numpy.bool_→bool refactor across 20+ render sites (contracts.py, mock.py, useRecipeSearchApi/CompareApi); removed BoolPill.vue; fixed recipe comparison & IDP mapping tests (1516 pass, typecheck/lint verified). Pushed openwiki regen; audited Progress.bento—76 API endpoints, 31–55k LOC (BE/FE/docs).

## 2026-07-27
Datatables (25 files, 12 adapters, 5 schemas); FDC 분석 refactor (9-task SDD, seq-axis scoped, split views, rows==fdc invariant); gallery (removed handoffs, pre-armed filter, unnamed params). Hardware picker (select-all/deselect, search-scoped, gridlines off); OpenSearch logging (8 fixes: admin/error/preflight/KST); recipe FTP (probe_recipe_ftp.py, office_example.py). Deploy verified (541 files, 1356 BE/839 FE tests ✓).

## 2026-07-26
Executed 18-parallel backend audit: recovered from clean-checkout regression (gitignored providers.office), merged 18 PRs fixing 4 prod bugs (parquet guards, static folder, SECRET_KEY quoting, ENDPOINTS gaps), validated 1321 backend + 765 frontend tests (7 ebeam gates). Completed FDC sparkline matrix (10-param CD-corr-rank, SequenceWorkbench, browser-verified). Refined mag-pixel SEM simulation edge-rendering; fixed i18n strings ("사내 기준" → "표준안"); DesignSync mag-pixel 2a (MetaBar, 1440px dense). Infrastructure: CLAUDE.md audit, provider-selection.md created, 34 skills disabled, typescript-lsp uninstalled.

## Identity Candidates
- IDENTITY CANDIDATE: Spec-driven sub-project sequencing with TDD + comprehensive testing (AFM A–D roadmap, Chat feature paired with dashboard polish)
- IDENTITY CANDIDATE: Design-system consolidation through accessor unification (SK_CHART, palette CIELAB/CVD audit, tables→descriptor)