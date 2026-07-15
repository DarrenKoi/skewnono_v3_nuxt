# Open Jobs

_Updated: 2026-07-15 · branch: main_

## In progress
- (none) — B1 측정 개요 shipped & pushed this session.

## Blocked
- (none)

## Backlog / soon
- [ ] B2 — Peer 비교 (`vs PEERS` card): auto same-recipe baseline + delta. Spec §8.1 constraints: exploratory set ≠ frozen baseline; `compatibility_signature`; explicit `mode=single|set` · since 2026-07-15
- [ ] B3 — FDC inline: connect orphan `Fdc*` components, CD↔`dynamic_fdc` on shared sequence axis, reuse `focusedSequence` (spec §12) · since 2026-07-15
- [ ] B3.2 — 하드웨어 timestamp popup: `useHardwareApi` eqp_id + start~end window → anchored slideover; as-of for MDC/SCE (spec §12) · since 2026-07-15
- [ ] §10.3 adaptive views: 위치 비교→공간 진단(single); Time-Series→시퀀스 추이(single); 상관/분포→param↔param(single). Reuses `focusedSequence` · since 2026-07-15
- [ ] B1 minors: keyboard/ARIA on clickable rows (MeasurementPoints/SiteVerdicts/DataSummary); stale comment `WaferMap.vue:26` (siteVerdicts no longer called there) · since 2026-07-15
- [ ] Mock realism: `cd_value` uniform [15,45] → leave-one-out flags ~80% of sites (noisy ◎). Tighten within-wafer spread (`back_dev_home/msr_file/data.py`) OR revisit site thresholds (Phase-A anomaly cfg) · since 2026-07-15
- [ ] Optional: skill-creator description eval on `/leave-office` + `/back-to-office`, then package · since 2026-06-30

## Closed today
- B1 측정 개요 SHIPPED (b3f9fb2..4f33581): answer-first layout, `overviewSites` single source, verdict strip + param navigator + linked selection, honesty gates; verified live cd-sem+hv-sem. Also: /leave↔/back-office loop exercised; `.remember/` committed (228f26d).

## Context to remember
- B1 spec `docs/superpowers/specs/2026-07-15-skewvoir-phase-b-measurement-overview-design.md` (§8.1 B2, §12 FDC/HW, §10.3 views); B1 plan `docs/superpowers/plans/2026-07-15-skewvoir-phase-b1-measurement-overview.md`.
- `overviewSites()` (`app/utils/overview.ts`) is the ONE analytics source; `focusedSequence` in `useSkewvoirAnalysis` is the shared linked-selection seam — B3/§10.3 reuse both. Integrity rule: every panel reads that source AND threads `anomalyCfg` (final review caught WaferMap re-deriving with a divergent config — fixed).
- Skewvoir `Fdc*` cluster is staged WIP — B3 connects it; don't prune.
- You run parallel git on main — it rebased my B1 commits twice mid-session (survived). For subagent-driven runs, a "pausing git" ping avoids racing pushes.
- Nuxt dev running REMOTE (task bx3sao973, `nuxt dev --host 0.0.0.0` :3000, Tailscale; Flask :5050 up). The 3 parallel-work commits (2d85e2b/f08088d/228f26d) carry Co-Authored-By: Claude — amending needs a force-push if unwanted.
