# Open Jobs

_Updated: 2026-07-24 · branch: main_

## In progress
- [ ] Wafer geometry `map_offset` coherence (Spec 1 of 2) — Tasks 1–4/7 done & reviewed; STOPPED at user request. Next: Task 5 = shift die-grid boundaries to `offset + (k+0.5)·pitch` (`front-dev-home/app/utils/waferDieGrid.ts:22`); get the brief via `scripts/task-brief docs/superpowers/plans/2026-07-24-wafer-geometry-map-offset-coherence.md 5`; ledger `.superpowers/sdd/progress.md`, Task 5 BASE `7e2781f` · since 2026-07-24
- [ ] Deploy packaging — plan written & committed (`1a7d33a`), NOT executed. Next: run Task 1 (hcputil fix, `back_dev_home/_auth/provider.py:32`) from `docs/superpowers/plans/2026-07-24-deploy-packaging.md`; user was choosing subagent-driven vs inline when session ended · since 2026-07-24
- [ ] Office verify recipe_tat + health (STATUS.md says 구현완료, never run on office data) — next: at office `cp office_example.py office.py` for sem_list/storage/recipe_tat; site auto-detects (PC* → office; sanity-check `python -c "from back_dev_home._runtime.site import detect_site; print(detect_site())"`), run office-mode contract tests, eyeball recipe 현황 (ranking composite/uncapped — watch first-load latency), bump STATUS.md → office + date · since 2026-07-21

## Blocked
- [ ] First cloud feasibility deploy → `http://skewnono-v3-webapp.aipp01.skhynix.com` — blocked on: packaging script (Tasks 1–7) shipping, then packing from the office PC · since 2026-07-24
- [ ] Confirm which `hcputil` SSO spelling the cloud image provides (`auth` vs `auto`) — blocked on: cloud host access; bundled `preflight.py` reports it on first run · since 2026-07-24
- [ ] Register `skewnono-v3-webapp.aipp01.skhynix.com` with SSO as a valid service/callback URL — blocked on: infra/SSO team; repeat for `skewnono.skhynix.com` at cutover · since 2026-07-24

## Backlog / soon
- [ ] Spec 2 — skewvoir paired-scatter field-location pairing: spec written (`docs/superpowers/specs/2026-07-24-skewvoir-field-location-pairing-design.md`), no plan yet; needs Spec 1 finished (uses `snapToDieCell`) · since 2026-07-24
- [ ] Set a real `SKEWNONO_SECRET_KEY` in `back_dev_home/.env` (still defaults to `dev-only-not-for-prod`); distinct values for test vs prod · since 2026-07-24
- [ ] Add `ProxyFix` — behind aipp01 ingress `request.remote_addr` is the proxy, so `_logging/activity.py` logs the proxy not the user · since 2026-07-24
- [ ] Rate limiter is `memory://` with `processes = 4` (`wsgi.ini`) — per-worker counters, effective limit ~4×; wants a Redis `storage_uri` · since 2026-07-24
- [ ] storage↔sem_list hidden coupling: `get_ppid_unavailable` joins via `sem_list.data.get_sem_list()` — STORAGE=office + SEM_LIST=mock silently empties rows; add provider-mismatch guard · since 2026-07-21
- [ ] Fix pre-existing `msr_file/tests/test_contract.py::test_office_adapter_raises_until_connected` (imports deleted office stub) · since 2026-07-21
- [ ] Wire next office features (16 pending mock-stub per STATUS.md; skew fab_name rename pending) · since 2026-07-21
- [ ] B2 — Peer 비교 (`vs PEERS` card): auto same-recipe baseline + delta. Spec §8.1: exploratory set ≠ frozen baseline; `compatibility_signature`; `mode=single|set` · since 2026-07-15
- [ ] B3 — FDC inline: connect orphan `Fdc*` components, CD↔`dynamic_fdc` on shared sequence axis, reuse `focusedSequence` (spec §12) · since 2026-07-15
- [ ] B3.2 — 하드웨어 timestamp popup: `useHardwareApi` eqp_id + start~end window → anchored slideover (spec §12) · since 2026-07-15
- [ ] §10.3 adaptive views (single-MSR variants of 위치/Time-Series/상관 panels) · since 2026-07-15
- [ ] B1 minors: keyboard/ARIA on clickable rows; stale comment `WaferMap.vue:26` · since 2026-07-15
- [ ] Mock realism: `cd_value` uniform [15,45] flags ~80% sites; tighten spread (`back_dev_home/msr_file/data.py`) · since 2026-07-15
- [ ] Optional: skill-creator eval on `/leave-office`+`/back-to-office` · since 2026-06-30

## Context to remember
- **Wafer map is mid-change — don't judge it yet.** Tasks 1–4 shifted die CENTRES and added `snapToDieCell`, but Task 5 (the grid overlay) has NOT landed, so the die grid still renders misaligned from the points. That's expected, not a regression.
- `map_offset` shifts the **die grid**, not the wafer: `stagePosMm` stays wafer-centre-relative because radius/sector depend on it (regression-pinned). The offset's sign/axis convention is still UNVERIFIED on screen — that's Task 7, and only the rendered map can settle it.
- **Spec 2's reason to exist:** the CD↔CD paired scatter joins on `chip_number#sequence`, which is wrong office-side — `sequence` is per-parameter measurement order, so two parameters never share it. It only "works" in Phase 1 because the mock emits every parameter inside one sequence loop.
- Three consecutive tasks shipped tests that passed against a *broken* implementation because a fixture offset was zero. Any further task here must prove its tests fail against a deliberately broken version.
- **Deploy's central gotcha:** `is_cloud()` is path-based (`/project/workSpace` prefix in `_runtime/env.py`) and `spa_dir()` walks `parents[2]`. Unpack anywhere else → no SSO auth, no SPA mount, mock data, while still serving HTTP 200. Bundle depth is load-bearing.
- The SPA calls `/api` relative and Flask serves it same-origin, so **one bundle works on both the aipp01 test URL and `skewnono.skhynix.com` — no rebuild at cutover.** Don't add CORS origins; don't set `SESSION_COOKIE_SECURE`/HSTS (both URLs are http-only).
- `hcputil` typo traces to `afm_data_platform/개발요구.txt:31` (a lossy transcription — also contains `reutrn`). User says the library is `auth`. Plan's fix tries both.
- Feasibility framing for the first deploy: a bundle serving **mock data is a success**; only a dead deploy is failure. That's why pack_deploy's checks are mostly advisory, with `--strict` for later.
- Error taxonomy: bare `LookupError` → JSON 502 (upstream data), bare `RuntimeError` → 503 (unconfigured); subclasses stay 500.
- Two sessions are live on `main` and keep interleaving commits (today: `1a7d33a` landed inside my Task-2 range). Re-read hunks before editing, stage explicit paths only, and never `git add -A` / `commit -a` / `stash`.
- Skewvoir seams unchanged: `overviewSites()` single analytics source; `focusedSequence` shared selection; `Fdc*` cluster is staged WIP — don't prune.
