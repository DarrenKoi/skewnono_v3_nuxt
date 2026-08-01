# Recent

## 2026-08-01
Shipped paraTrendSeries UI (20 tests, palette mutation-tested, legend/stacked defects fixed) and lotHealth subsystem (LotTable.vue, LotDetailModal.vue, coverage/rules/sort/filter/CSV). Designed multi-MSR Time-Series 3-panel layout (trend/distribution/tool-skew lenses) and fixed OKLCH a11y palette for paraColors (CVD 3.1→none, ΔE 10.2→≥15). Resolved skewnono param-pool URL-rewrite bug via pool-authority refactor (multi-set preserved, single-scope auto-corrects). Designed centralized scheduler runtime (11 TDD tasks for multi-worker dedup + Redis locking; Tasks 1-5 complete; 1006 tests pass).

## 2026-07-31
Shipped auth self-ID spec (5 tasks, 2014 tests): provider fallback, office-data sync via read_idp_info.py, identity chain verification, activity logging, IdentityPill UI. Fixed 302-redirect SSO field mapping (user_id→emp_no); implemented /api/me + member-directory (Redis LRU), wafer-map double-grid, rate-limiting. Verified 9 backend plumbing findings; identified 2 security issues. Merged 28-commit auth branch; cleaned 26 branches.

## 2026-07-30
Merged pending-tools→main, reordered office checklist, began IP separator change (newline→comma); removed staleness-threshold code (STALE_ARRIVAL_DAYS, 오래됨 badge, loadedAt), verified zero residuals. Completed ENMP readers, NUL escaping fixes, recipe-open tabs refactor; wired Redis adapters w/ 503 handlers (1827 tests). Shipped /tool-roster (fab×model matrix, 180-day pending-tools filter, IP-copy export) + /api/sem-list/pending; designed pending-tools spec, created inspection utilities (device_info/probe_planstep_r3/oper_order), implemented classifier.

## Identity Candidates
- IDENTITY CANDIDATE: Spec-driven sub-project sequencing with TDD + comprehensive testing (AFM A–D roadmap, Chat feature paired with dashboard polish)
- IDENTITY CANDIDATE: Design-system consolidation through accessor unification (SK_CHART, palette CIELAB/CVD audit, tables→descriptor)