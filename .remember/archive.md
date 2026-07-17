# Archive

## Week of 2026-07-14
Shipped X-ID access control (spec, JSON exceptions, admin middleware; 14+ tests, 8-agent review). Shipped skewvoir search (9-task SDD, OpenSearch 60d, FAB/EQ/date facets, 177 tests). UI polish: nav fixes, RecipeStatusView styling, AFM date display. Switched to Tailscale remote dev (tablet .ts.net), configured tmux.

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
Modified index.py to read PORT env var, resolved macOS AirPlay :5000 conflict. Verified Flask :5050 ↔ Nuxt :3100 proxy E2E. Diagnosed statusline-command.sh; presented zsh PROMPT customization options.

## Week of 2026-04-21
Created Flask+flask-cors venv for skewnono_v3_nuxt, started dev server :5000. Debugged macOS Python paths; resolved background task issues.
```