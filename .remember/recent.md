# Recent

## 2026-07-31
Shipped auth self-ID spec (5 tasks, 2014 tests): provider fallback, office-data sync via read_idp_info.py, identity chain verification, activity logging, IdentityPill UI. Fixed 302-redirect SSO field mapping (user_id→emp_no); implemented /api/me + member-directory (Redis LRU), wafer-map double-grid, rate-limiting. Verified 9 backend plumbing findings; identified 2 security issues. Merged 28-commit auth branch; cleaned 26 branches.

## 2026-07-30
Merged pending-tools→main, reordered office checklist, began IP separator change (newline→comma); removed staleness-threshold code (STALE_ARRIVAL_DAYS, 오래됨 badge, loadedAt), verified zero residuals. Completed ENMP readers, NUL escaping fixes, recipe-open tabs refactor; wired Redis adapters w/ 503 handlers (1827 tests). Shipped /tool-roster (fab×model matrix, 180-day pending-tools filter, IP-copy export) + /api/sem-list/pending; designed pending-tools spec, created inspection utilities (device_info/probe_planstep_r3/oper_order), implemented classifier.

## 2026-07-29
Completed recipe-IDP-Redis-locate spec (7 tasks, 42 steps): T1-6 (Redis locate, 1554 tests) and T9-11 (composables, 1603 BE + 871 FE tests); merged to main. Debugged Bento rendering (series.label, borderRadius); regenerated slides. Added align readers (16 tests, P.No→optics), extended FTP probe Stage D, fixed AlignPopup modal close-button. Code-review findings (502/503, HostFailure mock) resolved; cleaned 5 branches.

## Identity Candidates
- IDENTITY CANDIDATE: Spec-driven sub-project sequencing with TDD + comprehensive testing (AFM A–D roadmap, Chat feature paired with dashboard polish)
- IDENTITY CANDIDATE: Design-system consolidation through accessor unification (SK_CHART, palette CIELAB/CVD audit, tables→descriptor)