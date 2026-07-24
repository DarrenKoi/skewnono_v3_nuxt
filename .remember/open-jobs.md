# Open Jobs

_Updated: 2026-07-24 · branch: main_

## In progress
- [x] ~~Wafer geometry `map_offset` coherence (Spec 1 of 2)~~ — **DONE 2026-07-24**, all 7 tasks. Commits `e81227c` (Task 5 grid), `5a50542` (Task 6 mock coherence), `aef33da` (call-site wiring found by /simplify), `0ef5579` (comment fixes found by /code-review). Task 7 verified on screen: 0/74 points outside their die cell, 0/74 snapToDieCell mismatches, grid shifted 1.985 mm of a 6.977 mm pitch — **sign convention correct, no flip needed**. Screenshot `.playwright-mcp/screenshots/wafer-die-grid-map-offset.png` · Spec 2 is now unblocked
- [x] ~~Deploy packaging~~ — **DONE 2026-07-24**, all 7 tasks. `374432a` hcputil both-spellings fix (the boot blocker), `36b4123` preflight_cloud.py, `8657e69` bundle rules, `8d2eb54` office preflight, `09e7fa1` copy+verify, `465308b` manifest/runbook/CLI, `b25da1c` docs/deployment.md (KR) + CLAUDE.md, `6f2325d` review fixes. Verified: real bundle packs 506 files / 7.6 MiB, 6 office adapters in MANIFEST, `spa_dir()` resolves inside the bundle (depth invariant proven end to end), bundled `preflight.py` fails only on the PATH + hcputil checks locally, which is correct · **the packaging blocker for the first cloud deploy is cleared**
- [ ] Office verify recipe_tat + health — **PREPPED AT HOME 2026-07-24; only the on-site run is left.** Everything not requiring the company network is done:
  - `cp office_example.py office.py` — ALREADY DONE, all 6 adapters present.
  - Contract fixtures — refreshed to a clean **28/28** local baseline (`c7ce87a`). 4 had drifted, so an office run would have reported false failures. recipe_tat + health both pass, so their baseline is sound.
  - Blocker is purely network, proven twice: Redis `10.156.133.126:10121` → TimeoutError, and `.env` has no `OPENSEARCH_*` keys so `recipe_tat` office raises `OPENSEARCH_HOST is not set`. No route to `10.x` exists from here.

  **At the office, run:** `detect_site()` should print `office` (prints `home` here) → start Flask → `.venv/bin/python scripts/check_contract.py` (any FAIL is now a genuine office-side shape difference) → eyeball recipe 현황 (ranking is uncapped, `DEFAULT_LIMIT = 0` — watch first-load latency) → bump STATUS.md → office + date · since 2026-07-21

## Blocked
- [ ] First cloud feasibility deploy → `http://skewnono-v3-webapp.aipp01.skhynix.com` — packaging script now SHIPPED (2026-07-24), so this is unblocked on our side. Remaining: pack from the office PC (`npm --prefix front-dev-home run build && .venv/bin/python -m scripts.pack_deploy`), copy to `/project/workSpace/`, follow the bundle's `DEPLOY.md` · since 2026-07-24
- [ ] Confirm which `hcputil` SSO spelling the cloud image provides (`auth` vs `auto`) — no longer urgent: `_load_sso_class()` now tries BOTH (`374432a`), so either works. The bundled `preflight.py` still reports which one resolved, for the record · since 2026-07-24
- [ ] Register `skewnono-v3-webapp.aipp01.skhynix.com` with SSO as a valid service/callback URL — blocked on: infra/SSO team; repeat for `skewnono.skhynix.com` at cutover · since 2026-07-24

## Backlog / soon
- [ ] Spec 2 — skewvoir paired-scatter field-location pairing: spec written (`docs/superpowers/specs/2026-07-24-skewvoir-field-location-pairing-design.md`), no plan yet; needs Spec 1 finished (uses `snapToDieCell`) · since 2026-07-24
- [ ] Set a real `SKEWNONO_SECRET_KEY` in `back_dev_home/.env` (still defaults to `dev-only-not-for-prod`); distinct values for test vs prod · since 2026-07-24
- [ ] Add `ProxyFix` — behind aipp01 ingress `request.remote_addr` is the proxy, so `_logging/activity.py` logs the proxy not the user · since 2026-07-24
- [ ] Rate limiter is `memory://` with `processes = 4` (`wsgi.ini`) — per-worker counters, effective limit ~4×; wants a Redis `storage_uri` · since 2026-07-24
- [ ] storage↔sem_list hidden coupling: `get_ppid_unavailable` joins via `sem_list.data.get_sem_list()` — STORAGE=office + SEM_LIST=mock silently empties rows; add provider-mismatch guard · since 2026-07-21
- [x] ~~Fix pre-existing `msr_file/tests/test_contract.py::test_office_adapter_raises_until_connected`~~ — **DONE 2026-07-24** (`9e286b2`). That exact test was already retired; the real staleness was 8 sites across `tests/`. Whole backend suite now passes with no `--ignore`: **623 passed / 9 skipped / 0 failed**, and `tests/` went 21s → 0.9s
- [ ] Wire next office features (16 pending mock-stub per STATUS.md; skew fab_name rename pending) · since 2026-07-21
- [ ] B2 — Peer 비교 (`vs PEERS` card): auto same-recipe baseline + delta. Spec §8.1: exploratory set ≠ frozen baseline; `compatibility_signature`; `mode=single|set` · since 2026-07-15
- [ ] B3 — FDC inline: connect orphan `Fdc*` components, CD↔`dynamic_fdc` on shared sequence axis, reuse `focusedSequence` (spec §12) · since 2026-07-15
- [ ] B3.2 — 하드웨어 timestamp popup: `useHardwareApi` eqp_id + start~end window → anchored slideover (spec §12) · since 2026-07-15
- [ ] §10.3 adaptive views (single-MSR variants of 위치/Time-Series/상관 panels) · since 2026-07-15
- [ ] **Wafer map draws TWO disagreeing die grids** (found by /code-review 2026-07-24, confirmed on screen). `waferAxis.ts` sets `cfg.interval = pitchMm`, so ECharts steps split-lines from the axis ORIGIN and cannot be phase-shifted — they sit on the UNSHIFTED grid while `buildDieGridSegments` draws the shifted boundaries, ~17–20 px apart at 1400 px. Labels are still correct (`round((k·pitch − offset)/pitch) = k` holds while `|offset| ≤ 0.3·pitch`), so this is display coherence, not wrong data. Needs a UX call: turn the axis splitLine off when the die-grid overlay is on, or stop treating the axis as a die grid · since 2026-07-24
- [ ] B1 minors: keyboard/ARIA on clickable rows; stale comment `WaferMap.vue:26` · since 2026-07-15
- [ ] Mock realism: `cd_value` uniform [15,45] flags ~80% sites; tighten spread (`back_dev_home/msr_file/data.py`) · since 2026-07-15
- [ ] Optional: skill-creator eval on `/leave-office`+`/back-to-office` · since 2026-06-30

## Context to remember
- `map_offset` shifts the **die grid**, not the wafer: `stagePosMm` stays wafer-centre-relative because radius/sector depend on it (regression-pinned). Sign/axis convention **VERIFIED on screen 2026-07-24** — points sit inside their cells, no flip needed.
- **The test suite assumes you have NO office adapters.** `office.py` is gitignored, so tests that assert the "unconnected adapter" state only hold on a checkout without them. `tests/_office_state.py` encodes this: no adapter → assert the dispatcher's `RuntimeError`; adapter present → skip. If you add an adapter and a test suddenly fails with a Redis/OpenSearch timeout, it needs a guard, not a fix.
- **Office data cannot be reached from home** (verified 2026-07-24): company Redis `10.156.133.126:10121` times out off-network, and `.env` carries no `OPENSEARCH_*` keys at all, so `recipe_tat`'s office adapter raises `OPENSEARCH_HOST is not set`. Any office-verify job is genuinely office-only.
- **Spec 2's reason to exist:** the CD↔CD paired scatter joins on `chip_number#sequence`, which is wrong office-side — `sequence` is per-parameter measurement order, so two parameters never share it. It only "works" in Phase 1 because the mock emits every parameter inside one sequence loop.
- Three consecutive tasks shipped tests that passed against a *broken* implementation because a fixture offset was zero. Any further task here must prove its tests fail against a deliberately broken version.
- **Deploy's central gotcha:** `is_cloud()` is path-based (`/project/workSpace` prefix in `_runtime/env.py`) and `spa_dir()` walks `parents[2]`. Unpack anywhere else → no SSO auth, no SPA mount, mock data, while still serving HTTP 200. Bundle depth is load-bearing.
- The SPA calls `/api` relative and Flask serves it same-origin, so **one bundle works on both the aipp01 test URL and `skewnono.skhynix.com` — no rebuild at cutover.** Don't add CORS origins; don't set `SESSION_COOKIE_SECURE`/HSTS (both URLs are http-only).
- `hcputil` typo traces to `afm_data_platform/개발요구.txt:31` (a lossy transcription — also contains `reutrn`). User says the library is `auth`. Plan's fix tries both.
- Feasibility framing for the first deploy: a bundle serving **mock data is a success**; only a dead deploy is failure. That's why pack_deploy's checks are mostly advisory, with `--strict` for later.
- Error taxonomy: bare `LookupError` → JSON 502 (upstream data), bare `RuntimeError` → 503 (unconfigured); subclasses stay 500.
- Two sessions are live on `main` and keep interleaving commits (today: `1a7d33a` landed inside my Task-2 range). Re-read hunks before editing, stage explicit paths only, and never `git add -A` / `commit -a` / `stash`.
- Skewvoir seams unchanged: `overviewSites()` single analytics source; `focusedSequence` shared selection; `Fdc*` cluster is staged WIP — don't prune.
