# Open Jobs

_Updated: 2026-07-21 · branch: main_

## In progress
- [ ] Office verify recipe_tat + health (STATUS.md says 구현완료, never run on office data) — next: at office `cp office_example.py office.py` for sem_list/storage/recipe_tat (templates reshaped onto shared `_runtime/office_redis.py`); site auto-detects (PC* hostname → office, provider vars stay commented — sanity-check with `python -c "from back_dev_home._runtime.site import detect_site; print(detect_site())"`), run office-mode contract tests, eyeball recipe 현황 (ranking now composite/uncapped — watch first-load latency on wide ranges), then bump STATUS.md → office + date · since 2026-07-21
- [ ] Hostname site-detection UNCOMMITTED (`_runtime/site.py` + data_provider precedence + tests + .env.example/CLAUDE.md docs) — commit when user says so; add features to `OFFICE_READY` as they go live · since 2026-07-21

## Blocked
- (none)

## Backlog / soon
- [ ] storage↔sem_list hidden coupling: `get_ppid_unavailable` joins via `sem_list.data.get_sem_list()` — STORAGE=office + SEM_LIST=mock silently empties rows; add provider-mismatch guard/log (`storage/providers/office_example.py`) · since 2026-07-21
- [ ] Fix pre-existing `msr_file/tests/test_contract.py::test_office_adapter_raises_until_connected` (imports deleted office stub; retarget office_example or importorskip) · since 2026-07-21
- [ ] Wire next office features (16 pending mock-stub per STATUS.md; skew fab_name rename also pending per memory) · since 2026-07-21
- [ ] B2 — Peer 비교 (`vs PEERS` card): auto same-recipe baseline + delta. Spec §8.1: exploratory set ≠ frozen baseline; `compatibility_signature`; `mode=single|set` · since 2026-07-15
- [ ] B3 — FDC inline: connect orphan `Fdc*` components, CD↔`dynamic_fdc` on shared sequence axis, reuse `focusedSequence` (spec §12) · since 2026-07-15
- [ ] B3.2 — 하드웨어 timestamp popup: `useHardwareApi` eqp_id + start~end window → anchored slideover (spec §12) · since 2026-07-15
- [ ] §10.3 adaptive views (single-MSR variants of 위치/Time-Series/상관 panels, reuse `focusedSequence`) · since 2026-07-15
- [ ] B1 minors: keyboard/ARIA on clickable rows; stale comment `WaferMap.vue:26` · since 2026-07-15
- [ ] Mock realism: `cd_value` uniform [15,45] flags ~80% sites; tighten spread (`back_dev_home/msr_file/data.py`) or revisit thresholds · since 2026-07-15
- [ ] Optional: skill-creator eval on `/leave-office`+`/back-to-office` · since 2026-06-30

## Closed today
- Office wiring reviewed (2× two-axis /code-review) & hardened: ranking limit uncapped via composite agg, JSON 502/503 error handlers (+redis Timeout), TTL catalogs, "None"-string normalization, shared `_runtime/office_redis.py`, fabId→fabName sweep, datatables docs synced. Pushed through 1a87acb.

## Context to remember
- Error taxonomy convention: bare `LookupError` → JSON 502 (upstream data), bare `RuntimeError` → 503 (unconfigured); subclasses stay 500. New adapters follow it.
- device_desc / r3_device_grp carry literal "None" strings — `_text` in recipe_tat folds them; docs/datatables now warns. Standing rule: office schema info from user → sync docs/datatables/*.txt.
- A parallel session on main raced this one again today (fab_name sweep landed mid-edit; commit 904db65 swept my hunks in). Re-read hunks before editing when both panes are live.
- Skewvoir seams unchanged: `overviewSites()` single analytics source; `focusedSequence` shared selection; `Fdc*` cluster is staged WIP — don't prune. Spec/plan: `docs/superpowers/specs/2026-07-15-…-measurement-overview-design.md`, `docs/superpowers/plans/2026-07-15-…-b1-measurement-overview.md`.
