# Archive

## Week of 2026-07-21
Live-alarm broadcast (35 files, 1926 LOC, 746 tests, Redis ZSET + APScheduler), Chat LLM HCP gateway (3 models, E2E verified), Bento deck (Vue→Nuxt conversion). MSR image tool-FTP fetch (360+ tests, MinIO cache), BM/PM office adapter (57-58 tests, datatables), critical bugs fixed (PPID silent-drop, meas-hist >100%, chart zoom, beam-trend zoom, fdc_key casing). Provider layer infra: office Redis wiring, recipe_tat OpenSearch (15-field schema), storage adapter; skewvoir search bug, field-location Spec 1&2, deploy packer (Python allowlist). Code quality: dedup −121L, TS types, UI polish; Codex review (11 → 9-task SDD).

## Week of 2026-07-14
Shipped X-ID (14+ tests, 8-agent review), skewvoir (177 tests), AFM Sub-proj A (415 tests E2E), Chat backend (102 tests). Infrastructure: major office/home provider refactor (11 SKEWNONO_*_PROVIDER vars, 3-layer CLAUDE.md, office_example.py pattern), Ports & Adapters analysis, herdr hooks, TDD egress-guards (10 MIGRATION.md docs), openwiki cron (01:00, wrapper+launchd), localStorage consolidation (8 composables → factory), Redis adapter (office.py, env-based config), parquet fixes (5 commits), live office UI verified. Dashboard redesign (RadiusPlot, nav), skewvoir Phase B (wafer map, 236 tests), AFM A–D (458 tests). Pruned 42 specs, swept fonts, Tailscale remote.

## Week of 2026-07-07
Built office transition skills (/leave-office, /back-to-office); extended MSR file FDC mock with functional SkewvoirView integration. Swept design compliance: recipe-tat fonts (--sk-ink normalization), 장비상태 UI (40 NuxtUI tokens), echarts 6.1.0 CD outlier detection (97 tests). Designed BM/PM overlay + MDC time series redesign (10 subagent tasks); refactored recipe tables; switched to Tailscale remote dev.

## Week of 2026-06-30
Shipped network_sharpness_cdsem service with quarterly/daily tab UI. Designed and implemented CD outlier detection using median+MAD for skewvoir TimeSeriesChart with per-point recoloring (flags mean/spread anomalies). Dead-code cleanup pass on hardware/device-statistics and skewvoir (4 stale/export removals). 97 tests, 2 commits.

## Week of 2026-06-23
Merged feat/tool-skew-mgmt to main (+68 commits, 65 tests). Fixed Lucide icons for offline Windows by bundling 15 icons. Compacted device-statistics/measurement-rules UI (CapCell/Row/Matrix, reduced vertical spacing). Removed hardcoded --port from dev config; enabled NUXT_PORT env var. Fixed useRoute-in-middleware pattern in semaphore components. Added network_sharpness daily service with quarterly/daily tab grouping.

## Week of 2026-06-16
Locked skew-check terminology (fleet/consensus/residual/site-pool) and variance decomposition strategy. Refined skew-check logic (per-day median consensus, 10-meas/1wk window, 2wk max-lookback). Ported dev server 3100→3000. Drafted PM Up-gate spec (CD_MONITORING+BSM with fleet-skew advisory, no block).

## Week of 2026-05-25
Resolved compliance questions Q5/Q8 via grilling; drafted ADR 0004/0005 for memory class & permission rules. Fixed Nuxt port conflict (3100→3000) in dev setup. Completed Q7 matrix UI design and Q6/Q7-b monitoring spec.

## Week of 2026-04-28
Modified index.py to read PORT env var, resolved macOS AirPlay :5000 conflict. Verified Flask :5050 ↔ Nuxt :3000 proxy E2E. Diagnosed statusline-command.sh; presented zsh PROMPT customization options.

## Week of 2026-04-21
Created Flask+flask-cors venv for skewnono_v3_nuxt, started dev server :5000. Debugged macOS Python paths; resolved background task issues.