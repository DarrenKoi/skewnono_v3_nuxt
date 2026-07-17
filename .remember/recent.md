# Recent

```

# Recent

## 2026-07-16
Shipped skewvoir Phase B1 (wafer-map, radial, MSR drilldowns T0–T5, 26-chart PNG export), activity refactor (Fab-page), CompareToolPicker (MDC/SCE), selection-rail consolidation (AnalysisContextBar→LeftRail). Started mock→office backend (provider seams, T1–T10 done). Flask mock :5050. 386 tests ✓, live-verified.

## 2026-07-15
Executed skewvoir Phase B design (9 commits): multi-param navigator, linked selection, wafer map with Sites/Field modes, verdict strip, conditions panel. Built async MSR image-fetch system (vendored ftp_handler, disk cache, polling jobs, Redis worker pool). Redesigned analysis dashboard (compact layout, physical coordinates, param nav, stat bar, SEM viewer); swept app fonts (38 files, --sk-ink-muted normalization). Merged two feature branches; 236 frontend + 58 backend tests ✓.

## 2026-07-14
Shipped X-ID access control (spec, JSON exceptions, admin middleware; 14+ tests, 8-agent review). Shipped skewvoir search (9-task SDD, OpenSearch 60d, FAB/EQ/date facets, 177 tests). UI polish: nav fixes, RecipeStatusView styling, AFM date display. Switched to Tailscale remote dev (tablet .ts.net), configured tmux.

## Identity Candidates
- IDENTITY CANDIDATE: Systematic multi-phase shipping pattern (X-ID access control & skewvoir search: spec → comprehensive testing → multi-agent review → compliance/feature delivery)