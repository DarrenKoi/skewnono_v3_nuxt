# Recent

## 2026-08-07
Finalized chat RAG design & implementation plan (OpenSearch hybrid search, merged to main). Multi-fab Phase A approved (4 improvements: admin_logs, activity defaults, feature_ranking); Phase B designed (recipe-search tagging, live-alarm event stamping). Recipe-tat equipment-view API specified (2-endpoint design, 3 mock defects fixed via equipment-first refactoring); Sparkline→ECharts migration shipped (zoom-slider, TDD suite, 1237 tests✓).

## 2026-08-06
Validated GT2000 mags (600K–1000K); fixed AlignPopup freeze + office_example.py type handling. Fixed live-alarm feature mapping (policy comment, test coverage); designed manual search for chat (OpenSearch hybrid: Nori+BGE-M3+reranker; Evidence schema, AccessScope, deterministic IDs). Log-retention (7d cleanup) + uwsgi_reload (@00:05) jobs w/ registry.py tests; browser-tested, reload trigger complete.

## 2026-08-05
Row-card activity BE/FE (user-join + CSV export/search/sort); device-stats 전체 선택 + measurement header; param ordering fix & exemption refactors (outlier/job-type regex/DUMMY/bucket). Measurement rules palette/label refactor; IDP diagnostic tooling (path→bytes reader refactor, 287+ tests); admin page isAdmin-gating. 1200+ tests passing, merged main.

## Identity Candidates
- IDENTITY CANDIDATE: Spec-driven sub-project sequencing with TDD + comprehensive testing (AFM A–D roadmap, Chat feature paired with dashboard polish)
- IDENTITY CANDIDATE: Design-system consolidation through accessor unification (SK_CHART, palette CIELAB/CVD audit, tables→descriptor)
- IDENTITY CANDIDATE: Equipment-first mock refactoring for data consistency (fab vocab consolidation across multi-surface dashboards)