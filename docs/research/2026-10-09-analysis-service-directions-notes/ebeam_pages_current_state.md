# E-beam pages (excluding skewvoir and AFM), navigation shell and shared UI — current state as of 2026-10-09

Method note for the report writer. Source is the local repo at `main` `8d176861` (2026-10-09). Backend `contracts.py` files and mock module docstrings were read directly. The two page-value research docs were read in full. Frontend views were NOT read line by line: chart types, column names and labels below come from targeted greps over each view (ECharts `type: '…'`, `accessorKey`, label strings, download helpers, `route.query`). Where a claim rests on a grep rather than a full read it says so. Nothing was run; no browser, no office data. All paths are repo-relative.

## 1. Page-by-page inventory: what each page answers, its data, its analytics, its interactions

### Takeaway

Every listed feature is implemented end to end (page, composable, Flask blueprint, mock provider). The analytic depth is concentrated in four places — Recipe 현황 (mix-adjusted tool indices with confidence intervals), TTTM (client-side maximal-clique grouping, MDS/PCA map, PM tuning targets), 디바이스 통계/계측 룰 (client-side rule engine) and H/W 관리 (seven per-tool trend/compare panels). 장비 상태, 스토리지, Recipe 검색, 횡전개 and 측정 이력 are mostly tables over current-state or raw rows.

### Cited Findings

#### Routing facts that apply to all pages

- E-beam pages live under `/ebeam/{cd-sem|hv-sem}/[fab]/…`; `[fab]` may be a comma-joined multi-fab segment (`m14,r3`). — [frontend/app/utils/pageIdentity.ts](frontend/app/utils/pageIdentity.ts)
- Which tool family has which feature: `storage`, `recipe-search`, `recipe-status`, `hardware`, `live-alarm`, `skewvoir` exist for `cd-sem` and `hv-sem`; `device-statistics` and `tttm` are `cd-sem` only. — [frontend/app/utils/features.ts](frontend/app/utils/features.ts) (`FEATURE_TOOL_TYPES`)
- `device-statistics` and `skewvoir` are fab-less routes (`FABLESS_FEATURES`); `tttm` is the only single-fab page (`SINGLE_FAB_FEATURES`), where a multi-fab URL collapses to the primary fab. — [frontend/app/utils/features.ts](frontend/app/utils/features.ts)
- `/recipe-tat` and `/fail-issue` are redirects into `/recipe-status?tab=…`; `/pm-planning` is a redirect into `/tttm` (merged 2026-09-01). The backend folders `recipe_tat`, `fail_issue`, `pm_planning` remain separate features with their own endpoints. — [frontend/app/pages/ebeam/cd-sem/[fab]/recipe-tat/index.vue](frontend/app/pages/ebeam/cd-sem/%5Bfab%5D/recipe-tat/index.vue), [frontend/app/pages/ebeam/cd-sem/[fab]/pm-planning.vue](frontend/app/pages/ebeam/cd-sem/%5Bfab%5D/pm-planning.vue)
- `veritysem` and `provision` have only index/redirect pages; the landing page draws disabled tool cards with a `개발 예정` badge. — [frontend/app/pages/ebeam/veritysem/index.vue](frontend/app/pages/ebeam/veritysem/index.vue), [frontend/app/pages/index.vue](frontend/app/pages/index.vue)

#### Home / landing (`/`)

- Hub layout. Shows: multi-select fab picker (written to the navigation store via `setFabs`), one card per tool family with a tool count from `sem_list`, an AFM card, a per-family "online / total" status line (rows with `available === 'On'`), a backend health card, and a `미연결 장비 보기` button to `/tool-roster`. — [frontend/app/pages/index.vue](frontend/app/pages/index.vue), [frontend/app/components/home/BackendHealthCard.vue](frontend/app/components/home/BackendHealthCard.vue)
- The hub is deliberately not a ranked page: `resolvePage` returns `null` for `/`, so no page-view beacon fires. — [frontend/app/utils/pageIdentity.ts](frontend/app/utils/pageIdentity.ts)

#### 장비 상태 / sem_list (`/ebeam/<tool>/<fab>`, component `EbeamToolInventoryView`) and 미연결 장비 (`/tool-roster`)

- Backend: `GET /api/sem-list`, `GET /api/sem-list/pending`. `SemListRow` = `fac_id, eqp_id, eqp_model_cd, eqp_grp_id, vendor_nm, eqp_ip, fab_name, updt_dt, available (On/Off), version`. `updt_dt` is the tool's first arrival time at the fab, not an update time. `PendingToolRow` (roster minus reachable set) has no `available`/`version`. — [backend/sem_list/contracts.py](backend/sem_list/contracts.py), [backend/sem_list/routes.py](backend/sem_list/routes.py)
- Office source is three Redis parquet DataFrames (`v3_df_sem_list`, `v3_df_sem_avail`, `v3_df_sem_version`); the roster is a current snapshot, not a history. — [backend/sem_list/providers/mock.py](backend/sem_list/providers/mock.py)
- UI (grep): table columns Status, Equipment ID, Fab, Model, Vendor, IP Address, Version; Available/Offline and model filters; IP copy; a download helper is imported; each row links to skewvoir search via `skewvoirSearchRoute(toolType, { eq, fab })`. — [frontend/app/components/ebeam/ToolInventoryView.vue](frontend/app/components/ebeam/ToolInventoryView.vue)
- The row's "go to H/W" action still mutates shared state: `setSelectedTool(eqpId)` then navigates with no `eqp_id` in the URL. — [frontend/app/components/ebeam/ToolInventoryView.vue](frontend/app/components/ebeam/ToolInventoryView.vue) (lines 222, 243), [frontend/app/stores/navigation.ts](frontend/app/stores/navigation.ts)
- `/tool-roster`: pending (firewalled) tools grouped by family tabs (CD-SEM, HV-SEM, VeritySEM, Provision, 미분류) with Equipment ID, IP, Vendor, 반입일, Fac, Fab, Model, Group; a FAB × model matrix helper exists (`pendingToolMatrix.ts`). — [frontend/app/pages/tool-roster.vue](frontend/app/pages/tool-roster.vue), [frontend/app/utils/pendingToolMatrix.ts](frontend/app/utils/pendingToolMatrix.ts)

#### 스토리지 / storage (`/ebeam/<tool>/<fab>/storage`, sub-tab of 장비 상태)

- Backend: `GET /api/<tool_slug>/storage`, `GET /api/<tool_slug>/ppid-unavailable`. `StorageRow` = `eqp_id, eqp_ip, fac_id, total, used, avail, percent, storage_mt, rcp_counts, rcp_counts_mt, storage_mt_date, fab_name, eqp_model_cd` (capacity strings blank when collection failed). `PpidUnavailableRow` adds `missing_days_streak`. — [backend/ebeam/storage/contracts.py](backend/ebeam/storage/contracts.py), [backend/ebeam/storage/routes.py](backend/ebeam/storage/routes.py)
- Grain and freshness: one row per tool, refreshed by a 04:30 daily collector; no history is stored. — [backend/ebeam/storage/providers/mock.py](backend/ebeam/storage/providers/mock.py)
- UI (grep): tier filter (위험 ≥98%, 주의 90–97%, 정상 <90%, 정보 없음), 20 sort options, MetaBar counts (Total Tools, Critical, Warning, Healthy, Storage N/A), columns Equipment ID, Fab, Model, IP, Total, Used, Available, Usage, Recipes, Last Reported; a side panel lists PPID-unreachable tools with `Days Down`. Thresholds are constants `STORAGE_WARNING_THRESHOLD = 90`, `STORAGE_CRITICAL_THRESHOLD = 98`. — [frontend/app/components/ebeam/StorageView.vue](frontend/app/components/ebeam/StorageView.vue), [frontend/app/components/ebeam/storage/PpidUnavailablePanel.vue](frontend/app/components/ebeam/storage/PpidUnavailablePanel.vue), [frontend/app/utils/storageUsage.ts](frontend/app/utils/storageUsage.ts)
- Decision supported: which tool's disk or recipe count is near its limit, and which tools the PPID collector cannot reach.

#### Recipe 현황 = recipe_tat + fail_issue (`/ebeam/<tool>/<fab>/recipe-status?tab=tat|align|meas`)

- Shell: three tabs `Recipe TAT`, `Align Fail`, `Meas Fail`; `?tab=` is the source of truth. — [frontend/app/components/ebeam/RecipeStatusView.vue](frontend/app/components/ebeam/RecipeStatusView.vue)
- recipe_tat endpoints: `ranking`, `summary`, `daily-trend`, `devices`, `equipments`, `equipment-compare`. — [backend/ebeam/recipe_tat/routes.py](backend/ebeam/recipe_tat/routes.py)
- recipe_tat contracts: `RankingRow` (`rank, class_name, recipe_name, full_name, meas_counts, total_meastime, avg_meastime, sample_lot_cds, sample_eqp_ids, fab_names`), `SummaryPayload` (`anchor_date, total_tat_seconds, total_recipes, total_executions, avg_meastime`), `DailyTrendPoint` (`date, total_meastime, exec_count`), `DeviceRow` (per `lot_cd`, with `prod_catg_cd`/`tech_nm`), `EquipmentRow` (`exec_count, total_meastime, avg_meastime, recipe_count, top_recipe, top_recipe_share, tat_index, occupancy, usage_ratio`), `FleetReference` (medians plus p10–p90 `percentiles`), `EquipmentComparePayload` (per-tool daily trends and a recipe × tool cell table). — [backend/ebeam/recipe_tat/contracts.py](backend/ebeam/recipe_tat/contracts.py)
- `tat_index` = actual total TAT / TAT expected for that tool's recipe mix; `None` below `TAT_INDEX_MIN_SAMPLE = 12` executions (marked OFFICE-VERIFY). `occupancy` is explicitly "not MES utilisation" (sum of meastime, excludes loading/wait/PM). — [backend/ebeam/recipe_tat/contracts.py](backend/ebeam/recipe_tat/contracts.py)
- fail_issue endpoints: `summary`, `daily-trend`, `align-ranking`, `meas-ranking`, `devices`, `equipments`, `equipment-compare`. — [backend/ebeam/fail_issue/routes.py](backend/ebeam/fail_issue/routes.py)
- fail_issue contracts: `SummaryPayload` (`total_executions, align_fail_count/rate, align_na_count, meas_fail_count/rate, meas_fail_threshold, distinct_equipment/recipes/lots`), rankings by recipe (`AlignRankingRow`, `MeasRankingRow` with `avg_fail_ratio`), `EquipmentRow` with `align_expected`, `align_index`, `align_index_low/high` (Byar 95% interval, `CONFIDENCE_Z = 1.96`) and the same for meas; `FAIL_INDEX_MIN_EXPECTED = 1.0`. — [backend/ebeam/fail_issue/contracts.py](backend/ebeam/fail_issue/contracts.py)
- Meas-fail definition: a run whose `fail_ratio` exceeds `MEAS_FAIL_THRESHOLD = 15.0` (percent). — [backend/ebeam/fail_issue/providers/mock.py](backend/ebeam/fail_issue/providers/mock.py)
- UI (grep): each tab has views `전체 요약`, `디바이스별`, `장비별`. TAT: Top 10/20/30/50 selector, a daily line chart, a bar chart, ranking table (rank, full name, class, meas_counts, avg_meastime, total_meastime, share). Fail: chart modes Bar/Line/Ratio, ranking columns runs, fails, rate, avg ratio. 장비별: fleet table (eqp_id, fab, model, 실행수, 총 TAT, 평균, 레시피수) plus a compare panel with bar/line trends and a recipe × tool table. Download helpers are imported in `RecipeTatView`, `FailIssueView` and both equipment views. — [frontend/app/components/ebeam/RecipeTatView.vue](frontend/app/components/ebeam/RecipeTatView.vue), [frontend/app/components/ebeam/FailIssueView.vue](frontend/app/components/ebeam/FailIssueView.vue), [frontend/app/components/ebeam/RecipeTatFleetTable.vue](frontend/app/components/ebeam/RecipeTatFleetTable.vue), [frontend/app/components/ebeam/RecipeTatEquipmentCompare.vue](frontend/app/components/ebeam/RecipeTatEquipmentCompare.vue)
- Tool badges are a frontend display policy over backend numbers: TAT badges `느림 / 빠름 / 저사용 / 편중` use `USAGE_FLOOR = 0.85`, `TAT_FLOOR = 0.92`, `SHARE_CEIL = 0.50`, `TAT_CEIL = 1.10`, all marked OFFICE-VERIFY; fail badges (`weak / healthy / narrow`) require the confidence interval to exclude 1 AND a size constant. Badges are switched off for multi-fab queries because the peer group is the query scope. — [frontend/app/utils/equipmentSignals.ts](frontend/app/utils/equipmentSignals.ts), [frontend/app/utils/failEquipmentSignals.ts](frontend/app/utils/failEquipmentSignals.ts)
- Date range: presets today/7/14/30/60/90 days or free range, held in local component state; empty means the server's default 14 days from `anchor_date`. — [docs/research/2026-10-06-page-value-plans.md](docs/research/2026-10-06-page-value-plans.md) (S3 "지금 코드")
- Shipped 2026-10-06: each summary KPI shows its change against the previous same-length window (`recipeStatusDelta.ts`, `usePreviousWindowSummary.ts`). — commit `e382e300`, [frontend/app/utils/recipeStatusDelta.ts](frontend/app/utils/recipeStatusDelta.ts), [frontend/app/composables/usePreviousWindowSummary.ts](frontend/app/composables/usePreviousWindowSummary.ts)
- Mock: 55,000-row `meas_hist` universe shared by both features; tool fleet copied from `sem_list`; normal tool speed spread ±4%. Fail rates are fab-level scalars, so "per-tool difference does not exist" in the mock and badges cannot be reproduced reliably at home. — [backend/ebeam/recipe_tat/providers/mock.py](backend/ebeam/recipe_tat/providers/mock.py), [backend/ebeam/fail_issue/providers/mock.py](backend/ebeam/fail_issue/providers/mock.py)
- Decision supported: which recipe, device (lot_cd) or tool consumes measurement time or fails, and whether a tool is slow/failing beyond what its recipe mix explains.

#### Recipe 검색 / recipe_search (`…/recipe-search`), 열어보기 (`/open`), Recipe 비교 (`/compare`)

- Endpoints: `recipes`, `recipe-detail`, `parameters`, `measurement-points`, `measurement-locations`, `param-info`, `compare` (POST), `registry-check` (POST), `param-detail` (POST), `align-detail`, `align-images`, `recipe-image`. — [backend/ebeam/recipe_search/routes.py](backend/ebeam/recipe_search/routes.py)
- Contracts (465 lines): `RecipeSearchRow (recipe_name, fab_name)`, `RecipeDetailResponse (wafer_mp_info, wafer_align_info, idp_image_info, locator, …)`, `RecipeCompareResponse`, `ParamDetailResponse (amp, af_pr, images)`, `AlignImagesResponse`, `RecipeLocationsResponse (version, modified, parameter_rows, points)`. — [backend/ebeam/recipe_search/contracts.py](backend/ebeam/recipe_search/contracts.py)
- Office side: only the recipe NAME LIST is a Redis hash per family, refreshed daily; fab vocabulary is `fab_name` (M16A), never `fac_id`. — [backend/ebeam/recipe_search/providers/mock.py](backend/ebeam/recipe_search/providers/mock.py)
- Search UI: whitespace/underscore tokenised AND search; an in-table live filter; when a 3+ character lookup matches nothing it probes `meas_hist` (about 15 minutes fresh) so a just-created recipe is not mistaken for a typo; a registry check upgrades fallback rows; URL carries `q`, `page`, `size`. — [frontend/app/components/ebeam/RecipeSearchView.vue](frontend/app/components/ebeam/RecipeSearchView.vue)
- Persisted per tool type: recent searches and a recipe working set (the compare cart). — [frontend/app/composables/useRecipeRecentSearches.ts](frontend/app/composables/useRecipeRecentSearches.ts), [frontend/app/composables/useRecipeSelectionSet.ts](frontend/app/composables/useRecipeSelectionSet.ts)
- 열어보기: IDP table, tabs `이미지 + 설정`, `AMP`, `Sequence`, `측정 위치`, an Align popup, image lightbox with cond-mark overlays, Excel download (optionally including addressing images). — [frontend/app/components/ebeam/RecipeOpenView.vue](frontend/app/components/ebeam/RecipeOpenView.vue), [frontend/app/components/ebeam/recipeOpen/](frontend/app/components/ebeam/recipeOpen)
- Recipe 비교: parameter overlap/coverage classification, IDP field and setting-row diffs (`cellsDiffer`), image slots, workbook export (`buildCompareWorkbook`); constants `GROUPING_DEFAULT_THRESHOLD = 8`, `OUTLIER_SHARE = 0.25`. — [frontend/app/utils/recipeCompare.ts](frontend/app/utils/recipeCompare.ts), [frontend/app/components/ebeam/RecipeCompareView.vue](frontend/app/components/ebeam/RecipeCompareView.vue)
- Decision supported: find a recipe, read its configuration, and see how two or more recipes differ in configuration. No result data is joined.

#### 횡전개 / lateral_recipe (`…/recipe-search/lateral`)

- Endpoint `GET /api/<tool_slug>/recipe-search/lateral`. `LateralRecipeResponse` = `total_tools_in_fab, ready_count, not_ready_count, latest_recipe_version, latest_generated_at, versions[{recipe_version, generated_at, ready_count}], rows[{eqp_id, eqp_model_cd, vendor_nm, available, recipe_ready, recipe_version, recipe_generated_at}]`. — [backend/ebeam/lateral_recipe/contracts.py](backend/ebeam/lateral_recipe/contracts.py)
- Office source is OpenSearch `cdsem_idp_ver` / `hvsem_idp_ver`, one doc per (recipe, version); the roster comes from `sem_list`; a tool that executed the recipe in the last 30 days cannot be shown as 미보유. — [backend/ebeam/lateral_recipe/providers/mock.py](backend/ebeam/lateral_recipe/providers/mock.py)
- UI (grep): 보유/미보유 split, counts (Total tools, Recipe 보유), table of eqp_id, model, avail; rows grouped by version. — [frontend/app/components/ebeam/RecipeLateralView.vue](frontend/app/components/ebeam/RecipeLateralView.vue), [frontend/app/utils/lateralVersionGroups.ts](frontend/app/utils/lateralVersionGroups.ts)
- Decision supported: which tools hold this recipe and at which version.

#### 측정 이력 / meas_hist (`…/recipe-search/meas-hist`)

- Endpoints: `GET /api/meas-hist`, `/meas-hist/search`, `/meas-hist/facets`, `/meas-hist/window`. — [backend/meas_hist/routes.py](backend/meas_hist/routes.py)
- `MeasHistRow` = `id, fac_id, fab_name, vendor_nm, eqp_id, eqp_ip, eqp_model_cd, tool_type, lot_cd, lot_id, class_name, recipe_name, full_name, timestamp, start_time, end_time, meastime (s), msr, msr_check (Yes/No), align_fail (Pass/Fail/NA), total_images, fail_images, fail_ratio (percent 0..100), idp_name, idw_name`. Grain: one row per measurement execution. — [backend/meas_hist/contracts.py](backend/meas_hist/contracts.py)
- Retention: `RETENTION_DAYS = 60`; the 측정 이력 tab uses a narrower window than retention. Office source is OpenSearch aliases `meas_hist_cdsem` / `meas_hist_hvsem`; this is "the most widely read office source in the project" (meas_hist, recipe_tat, fail_issue, msr_file, lateral_recipe). Office timestamps are offset-less KST treated as UTC. — [backend/meas_hist/providers/mock.py](backend/meas_hist/providers/mock.py)
- `/meas-hist/window` returns one tool's measurements overlapping a window around a hardware timestamp, with a `capped` flag. — [backend/meas_hist/contracts.py](backend/meas_hist/contracts.py)
- UI (grep): one summary line (Total, MSR 없음, Align Fail, Avg fail ratio) and a table (timestamp, eqp_id, class, recipe, msr, align, images, fail, ratio, lot_id, meas(s)); view threshold `MEAS_FAIL_THRESHOLD = 15`. — [frontend/app/components/ebeam/RecipeMeasHistView.vue](frontend/app/components/ebeam/RecipeMeasHistView.vue)
- Shipped 2026-10-06: each row's MSR links to the skewvoir analysis page. — commits `edb5c692`, `5e8de525`, [frontend/app/utils/skewvoirLinks.ts](frontend/app/utils/skewvoirLinks.ts)
- The office adapter caps at `size=10000` so `rows` can be fewer than `total`, with no `capped` flag on this endpoint. — [docs/research/2026-10-06-page-value-plans.md](docs/research/2026-10-06-page-value-plans.md) (S4 "지금 코드")

#### H/W 관리 / hardware (`…/hardware`)

- One endpoint: `GET /api/<tool_slug>/hardware/<eqp_id>/<service>` with `service ∈ {bsm, reso-center, fdc, fdc-fleet, mdc, sce, bm-pm, sharpness}`. `HardwarePayload` is generic: `cards` (with `tone`), `tables`, `docs` (raw time-series), `settings` (dict-of-dict for the tool and in-fab siblings), `fleet` (`FdcFleet`: per-tool chuck temperature, laser x1/y1, contact-pin judgment counts, counter rates, margin histogram). — [backend/ebeam/hardware/routes.py](backend/ebeam/hardware/routes.py), [backend/ebeam/hardware/contracts.py](backend/ebeam/hardware/contracts.py)
- Seven tabs in two cadence groups: 데일리 = FDC, Sharpness (chamber stub sample, every 6–8 hours); 분기 = BM/PM, BSM (Beam Shape Matching), Reso Center, MDC (Meas Data Correction), SCE (Sharpness Characteristic Equalizer). Window presets: daily 2/3/4 weeks, quarterly 30/60/90 days. — [frontend/app/components/ebeam/HardwareView.vue](frontend/app/components/ebeam/HardwareView.vue)
- The page reads `?eqp_id=`, `?start=`, `?end=` once at setup. — [frontend/app/components/ebeam/HardwareView.vue](frontend/app/components/ebeam/HardwareView.vue)
- Per-panel chart types (grep of ECharts series): FDC line + scatter with markLine/markArea and a per-tool vs `Fab 전체` toggle; FDC fleet view heatmap / trend line / scatter / bar; Sharpness line profile; BSM radar + trend line; Reso Center scatter + line; MDC scatter + boxplot with tables (value, `median 대비`, `fleet 범위 (ppm)`, change history `이전/이후/변경 (ppm)`); SCE line / radar with sibling comparison and collection-date history; BM/PM `예정` and `이력` tables. — [frontend/app/components/ebeam/hardware/](frontend/app/components/ebeam/hardware)
- Supporting pure functions: laser outliers at `LASER_OUTLIER_SIGMA = 3`; MDC families/trajectories/changes; SCE harmonics and setting diffs; BM/PM events drawn as chart mark lines; compare-tool colour assignment and box points. — [frontend/app/utils/fdcLaser.ts](frontend/app/utils/fdcLaser.ts), [frontend/app/utils/mdcHistory.ts](frontend/app/utils/mdcHistory.ts), [frontend/app/utils/sceCompare.ts](frontend/app/utils/sceCompare.ts), [frontend/app/utils/bmPmMarkers.ts](frontend/app/utils/bmPmMarkers.ts), [frontend/app/utils/hardwareCompare.ts](frontend/app/utils/hardwareCompare.ts)
- Drill-down: picking a time on an FDC/Sharpness chart opens a slide-over of the recipes measured around that time (via `/meas-hist/window`), each linking to 측정 이력 through `recipeDetailRoute(...)`. — [frontend/app/components/ebeam/hardware/RecipeWindowSlideover.vue](frontend/app/components/ebeam/hardware/RecipeWindowSlideover.vue)
- BM/PM office sources are two OpenSearch indices: `fab_inform_notes` (maintenance that happened, past 180 days, with free-form engineer notes) and a plan index. — [backend/ebeam/hardware/providers/bm_pm/mock.py](backend/ebeam/hardware/providers/bm_pm/mock.py)
- Download helpers are imported only in `BsmPanel.vue` and `SharpnessPanel.vue` among hardware panels (grep). — [frontend/app/components/ebeam/hardware/BsmPanel.vue](frontend/app/components/ebeam/hardware/BsmPanel.vue), [frontend/app/components/ebeam/hardware/SharpnessPanel.vue](frontend/app/components/ebeam/hardware/SharpnessPanel.vue)
- Recent fixes show the page is in active use/maintenance: MDC/SCE compare tools limited to picked models, BM/PM history ordered newest first, FDC chuck-temperature heatmap shows every tool name (2026-10-06); FDC LaserPower `전체 보기` toggle (2026-10-03). — commits `1443b56b`, `390036d6`, `d8f10e11`, `877b8833`

#### 라이브 알람 / live_alarm (`…/live-alarm`, reached from the 실험실 menu)

- Endpoint `GET /api/<tool_slug>/live-alarm`. `AlarmEvent` = `id, rawid, eqp_id, alarm_modelname, alid, al_code, al_type, kind (align|meas), alarm_name, occurred_at, occurred_epoch, lot_id, cassette_id, recipe_id, ppid, operation_desc, step_id, lot_type_cd, meseventname, eq_stat, fab_name`. Payload adds `feed_status (live|stale|not_configured)`, `fetched_at`, `covered_since`, `unmatched_count`, `not_configured_fabs`. — [backend/ebeam/live_alarm/contracts.py](backend/ebeam/live_alarm/contracts.py)
- Time range: board window `BOARD_WINDOW_SEC = 1200` (20 minutes, widened from 10 on 2026-08-07 because alarms fell off before triage finished); Redis keeps `PRUNE_SEC = 1800`; `CACHE_TTL_SEC = 20`. Only three Hitachi alarm ids are rendered: 9006 (align), 9007 and 9035 (meas); AMAT codes are unknown. — [backend/ebeam/live_alarm/contracts.py](backend/ebeam/live_alarm/contracts.py)
- The board is refreshed on demand by viewers, not by a writer service. — [backend/ebeam/live_alarm/contracts.py](backend/ebeam/live_alarm/contracts.py) (module docstring)
- UI (grep): filter `전부 보기 / Align Fail만 / 측정 실패만` (persisted), feed status label, MetaBar stats (Align Fail, 측정 실패, 관련 lot), per-event rows (LOT, FOUP, STEP, 이벤트, 상태), meas events grouped by `(eqp_id, ppid)`, an Align images modal, and a recipe link built by hand to `…/recipe-search?q=<recipe_id>`. — [frontend/app/components/ebeam/LiveAlarmView.vue](frontend/app/components/ebeam/LiveAlarmView.vue), [frontend/app/components/live-alarm/AlarmRow.vue](frontend/app/components/live-alarm/AlarmRow.vue), [frontend/app/composables/useLiveAlarmFilter.ts](frontend/app/composables/useLiveAlarmFilter.ts)
- Shipped 2026-10-06: a 사건 범위 card with three columns — `한 recipe · 여러 장비`, `한 장비 · 여러 recipe`, `한 lot · 여러 장비`. — commits `aba5774b`, `a6f2b998`, [frontend/app/components/live-alarm/ScopePanel.vue](frontend/app/components/live-alarm/ScopePanel.vue)
- Mock fabricates a hot `(tool, recipe)` burst and one lot failing on two tools on every non-empty board; both rates are OFFICE-VERIFY. — [backend/ebeam/live_alarm/providers/mock.py](backend/ebeam/live_alarm/providers/mock.py)

#### 장비간 스큐(TTTM) + PM 튜닝 / tttm + pm_planning (`/ebeam/cd-sem/<fab>/tttm`, 실험실 menu, cd-sem only)

- Endpoints: `GET /api/<tool_slug>/tttm/check`, `GET /api/<tool_slug>/tttm/recipes`, `GET /api/<tool_slug>/pm-planning/fleet`. — [backend/ebeam/tttm/routes.py](backend/ebeam/tttm/routes.py), [backend/ebeam/pm_planning/routes.py](backend/ebeam/pm_planning/routes.py)
- `TttmCheckPayload` carries raw per-cell pairwise skew matrices (`occupied_cells[]` with `beam_condition, axis, cd_band, median_cd_nm, mdc_epoch, tier (direct|predicted), confidence, direct/predicted_skew_matrix`), `parameter_profile` (tool × parameter offsets from fleet median), `fleet_today` (matrix + `consensus_deviation`), `trend[{eqp_id, date, skew}]`, `epoch_markers` (hard = MDC changed, soft = BM/PM), `mdc_history`, `production_corroboration`, `current_tolerance`, `tolerance_range`. "The client computes N배화 (maximal-clique) grouping; the server never groups." — [backend/ebeam/tttm/contracts.py](backend/ebeam/tttm/contracts.py)
- Tolerance: `TOLERANCE_RANGE = {min 0.01, max 0.2, step 0.005}`, `DEFAULT_TOLERANCE = 0.05`, in monitor-wafer nm that the client scales per cell by measured CD; the fab's action limit is 1% of CD. — [backend/ebeam/tttm/contracts.py](backend/ebeam/tttm/contracts.py), [frontend/app/utils/tttmLimits.ts](frontend/app/utils/tttmLimits.ts) (`PM_BM_ACTION_LIMIT_RATIO = 0.01`, `MONITOR_WAFER_CD_NM = 15`, `MEASUREMENT_FLOOR_NM = 0.05`)
- Window: `WINDOW_WEEKS_CHOICES = (1, 2, 3, 4)`, default 2. — [backend/ebeam/_analysis_window.py](backend/ebeam/_analysis_window.py)
- Recipe picker lists only recipes the fab actually measured, with `runs` and distinct `tools`. — [backend/ebeam/tttm/contracts.py](backend/ebeam/tttm/contracts.py) (`TttmRecipeRow`)
- pm_planning `FleetPayload`: per tool a `GateBlock` (`cd_monitoring_value`, `cd_spec_lower/upper`, `cd_in_spec`, `bsm_in_spec`, `bsm_sharpness_avg`, `bsm_noise_avg`, `post_pm_at`, `prev_post_delta`, `mdc_changed`, `verdict up|hold`), per-cell `CellSkew` (beam 500V/800V × axis X/Y) and `epoch_history`. The two spec inputs of the Up gate are fabricated in the mock (OFFICE-VERIFY). — [backend/ebeam/pm_planning/contracts.py](backend/ebeam/pm_planning/contracts.py), [backend/ebeam/pm_planning/providers/mock.py](backend/ebeam/pm_planning/providers/mock.py)
- UI flow: pick recipe → pick tools by model group → pick 수집 기간 and press 데이터 요청 → pick parameters, panels and tolerance. Panels: `RecommendationCard`, `FleetMap`, PM `Targets`, `FleetStatus`, `ExcludedTools`, `PairMatrix`, `TrendChart`, `MdcTimeline`. — [frontend/app/components/ebeam/LabView.vue](frontend/app/components/ebeam/LabView.vue), [frontend/app/components/ebeam/tttm/](frontend/app/components/ebeam/tttm)
- Client-side engines: Bron–Kerbosch maximal cliques and adjacency by tolerance (`tttmGrouping.ts`), classical MDS with Jacobi eigen (`fleetMap.ts`), PCA over the parameter profile (`parameterPca.ts`), leave-one-out tuning targets per parameter (`pmTuningTarget.ts`), cell admission report (`pmAdmission.ts`). — [frontend/app/utils/tttmGrouping.ts](frontend/app/utils/tttmGrouping.ts), [frontend/app/utils/fleetMap.ts](frontend/app/utils/fleetMap.ts), [frontend/app/utils/parameterPca.ts](frontend/app/utils/parameterPca.ts), [frontend/app/utils/pmTuningTarget.ts](frontend/app/utils/pmTuningTarget.ts), [frontend/app/utils/pmAdmission.ts](frontend/app/utils/pmAdmission.ts)
- Persisted: scope/settings per (tool type, fab) and the panel selection once per page. — [frontend/app/composables/useTttmSettings.ts](frontend/app/composables/useTttmSettings.ts), [frontend/app/composables/useLabPanels.ts](frontend/app/composables/useLabPanels.ts)
- Mock: one latent bias per tool drives every view; the last tool of the roster is the drifted one. — [backend/ebeam/tttm/providers/mock.py](backend/ebeam/tttm/providers/mock.py)
- Decision supported: which tools form an interchangeable (N배화) group at a tolerance, which tool is the outlier, and where to move one tool during a PM window.

#### 디바이스 통계 / device_statistics (`/ebeam/cd-sem/device-statistics`, `/comparison`, `/measurement-rules`)

- Endpoints (all under `/api/cdsem/device-statistics/`): `r3-device-grp`, `device-desc`, `meas-activity`, `recipe-statistics`, `recipe-params`, `rules`, `recipe-trend`. — [backend/ebeam/device_statistics/routes.py](backend/ebeam/device_statistics/routes.py)
- Contracts: device catalogues (`R3DeviceGrpRow`, `DeviceDescRow` incl. `rnd_connector`), `MeasActivityRow (lot_cd, meas_count)` over 90 days, `ParaBlock` (parameter counts by point-count bucket `para_5/9/13/16/over_16` and percents), `RecipeInfoRow` (one row per (lot, oper_seq, samp_seq) step with `recipe_id`, `eqp_id`, `skip_yn`), `SummaryRow` (`total_recipe, avail_recipe`), `TrendBucket` (weekly snapshots, four buckets), `RecipeParamsRow` (`recipe_class, family, phase, memory_class_auto, parameters[{name, point_count, mother, region}]`), `RuleCell` (`selector`, `caps` per type, `name_overrides`), `Thresholds (yellow_at, red_at)`. — [backend/ebeam/device_statistics/contracts.py](backend/ebeam/device_statistics/contracts.py)
- Selection page: fab pills R3/M16/M15/M14/M11/M10, grouped filter cards, lot rows (Lot, Meas (90d), Grade plus catalogue attributes), a cart and saved presets, download. — [frontend/app/pages/ebeam/cd-sem/device-statistics/index.vue](frontend/app/pages/ebeam/cd-sem/device-statistics/index.vue), [frontend/app/composables/useDevicePresets.ts](frontend/app/composables/useDevicePresets.ts)
- Analysis page (`디바이스 분석`): bucket switch All / Only Normal / Mother Normal / Only Sample, stacked parameter-distribution bars, lot summary table (lot, stage, health, 상한 초과, 판정 범위, para 분포, para 합계, 운용 recipe, 전체 recipe, 중앙값, 중앙값 초과 파라미터, description), lot detail modal (sort 공정순/recipe 이름, filter 전체/초과만), step outlier cards, weekly `파라미터 추이` line chart (개별/누적). — [frontend/app/pages/ebeam/cd-sem/device-statistics/comparison.vue](frontend/app/pages/ebeam/cd-sem/device-statistics/comparison.vue), [frontend/app/components/cdsem/comparison/](frontend/app/components/cdsem/comparison)
- 계측 룰 page: "R3 계측 파라미터 cap 정책과 준수 결과" — rule matrix, compliance table (`R3 룰 준수`, downloadable), drill slide-over. — [frontend/app/components/ebeam/MeasurementRulesView.vue](frontend/app/components/ebeam/MeasurementRulesView.vue), [frontend/app/components/ebeam/rules/ComplianceTable.vue](frontend/app/components/ebeam/rules/ComplianceTable.vue)
- Judgement is client-side: `ruleEngine.evaluateLot` against server-supplied rules; M-fab lots get `no-rules` (no invented caps). — [frontend/app/utils/lotHealth.ts](frontend/app/utils/lotHealth.ts), [frontend/app/utils/ruleEngine.ts](frontend/app/utils/ruleEngine.ts)
- Shipped 2026-10-06: per-recipe "판정 근거" explanation (`ruleExplain.ts`, `devstat/RecipeExplain.vue`). — commits `3b53d1d8`, `5d22b58b`, `c5ca346d`, [frontend/app/utils/ruleExplain.ts](frontend/app/utils/ruleExplain.ts)
- Domain rules: a measurement rule is a per-type point-count CAP (under-measurement is not a violation); rules are edited by changing `providers/rules.py` and deploying, in-app save/history/rollback was dropped (grilling-log D12); analysis scope is one fab; lot is the primary axis; operator and executive share one URL. — [CONTEXT.md](CONTEXT.md), [docs/adr/0001-lot-as-primary-axis.md](docs/adr/0001-lot-as-primary-axis.md), [docs/adr/0002-shared-url-across-audiences.md](docs/adr/0002-shared-url-across-audiences.md)
- Decision supported: which lots/recipes measure more points than the rule allows (a TAT optimisation lever), per owning team.

#### 채팅 / chat (`/chat`, 실험실 menu)

- Endpoints: `availability`, thread CRUD, `POST …/messages`, feedback PUT/DELETE, `figures/<figure_id>`. — [backend/chat/routes.py](backend/chat/routes.py)
- The app has no LLM of its own: `runtime` is `rag` or `scope_rejection`. A turn stores `sources` (cited `Evidence` of type manual/meeting/email/report), `tool_traces`, `rewrite`, `follow_ups`, `attachments` (tables/charts from data tools), and user feedback with reason codes. — [backend/chat/contracts.py](backend/chat/contracts.py)
- Structured-data tools published to the RAG: exactly three — `recipe_tat_daily_trend`, `fail_issue_summary`, `fail_issue_daily_trend`; results are dataframe dicts capped at `ROW_LIMIT = 200`; "Aggregates before rows … Raw listings wait." — [backend/chat/data_tools.py](backend/chat/data_tools.py)
- UI: sidebar of threads, thread view, composer, sources, attachments, feedback controls; polling picks up a turn in flight. — [frontend/app/pages/chat.vue](frontend/app/pages/chat.vue), [frontend/app/components/chat/](frontend/app/components/chat)

#### Mag/Pixel 가이드 (`/mag-pixel`, 실험실 menu) — outside the listed features, noted for completeness

- A calculator (필요 FOV nm, 추천 MAG, 픽셀) that makes no API calls. — [frontend/app/pages/mag-pixel.vue](frontend/app/pages/mag-pixel.vue), [backend/activity/providers/mock.py](backend/activity/providers/mock.py) (docstring: "Some pages (mag-pixel) make no API calls at all")

### Inferences

- (inference) The pages split into three kinds: "state of the fleet now" (장비 상태, 스토리지, 횡전개, 라이브 알람), "aggregates over a 14–90 day window of meas_hist" (Recipe 현황, 측정 이력), and "configuration readers" (Recipe 검색/열어보기/비교, 디바이스 통계/계측 룰). Only H/W 관리 and TTTM look at measured physical quantities (beam, CD skew) on these pages; measured CD values themselves are otherwise confined to skewvoir.
- (inference) Because fail_issue's mock has no per-tool variation and recipe_tat's badge constants are all OFFICE-VERIFY, the tool-badge layer is the least validated analytic on these pages; its real behaviour is only knowable at the office.
- (inference) pm_planning's Up-gate verdict depends on spec inputs that are fabricated in the mock, so the "up/hold" decision support is not yet grounded in a confirmed office spec source.

### Gaps

- Frontend views were characterised by grep, not full reads. Exact layouts, empty states, and whether each chart draws limit/reference lines were not verified. The `markLine` hits in hardware panels may be BM/PM event markers rather than spec limits; `backend/ebeam/hardware/contracts.py` defines no spec-limit field, but per-service raw `docs` were not inspected for embedded limits.
- Which features have a working office adapter today was not established from code (office adapters are gitignored `office.py` copies). Project memory says sem_list and storage are office-verified and others are templated; that was not re-checked here.
- `docs/api-contracts/*.yaml`, `docs/datatables/*` and each `MIGRATION.md` were not read; they may list further office fields not surfaced in `contracts.py`.

## 2. Which analytics are computed, and where (backend vs frontend)

### Takeaway

Backend computes aggregates, expected-value indices and percentile summaries for Recipe 현황 and raw matrices for TTTM; nearly every judgement (badges, grouping, rule compliance, deltas, alarm scoping) is a pure TypeScript function in `frontend/app/utils/` with a `node --test` file beside it. There is no SPC control chart, no Cp/Cpk, no forecasting and no stored baseline anywhere on these pages.

### Cited Findings

- Backend: recipe/device/tool aggregation, daily trend, `tat_index` (actual vs recipe-mix-expected), `occupancy`, `usage_ratio`, fleet medians and p10–p90 percentiles. — [backend/ebeam/recipe_tat/contracts.py](backend/ebeam/recipe_tat/contracts.py), [backend/ebeam/_analytics.py](backend/ebeam/_analytics.py) (`percentile_summary`)
- Backend: fail counts/rates, expected fails per tool, fail index with Byar 95% interval. — [backend/ebeam/fail_issue/contracts.py](backend/ebeam/fail_issue/contracts.py)
- Backend: FDC fleet aggregations (window means, per-day temperature, pin counter rates, margin histogram). — [backend/ebeam/hardware/contracts.py](backend/ebeam/hardware/contracts.py)
- Backend: TTTM pairwise skew matrices per cell, consensus deviation, parameter profile; pm_planning gate inputs and consensus per cell. Grouping, ranking and thresholding are explicitly client-side. — [backend/ebeam/tttm/contracts.py](backend/ebeam/tttm/contracts.py), [backend/ebeam/pm_planning/contracts.py](backend/ebeam/pm_planning/contracts.py)
- Backend: device_statistics parameter-count buckets and weekly snapshots. — [backend/ebeam/device_statistics/contracts.py](backend/ebeam/device_statistics/contracts.py)
- Frontend: tool badges (percentile AND absolute constant for TAT; interval AND constant for fails). — [frontend/app/utils/equipmentSignals.ts](frontend/app/utils/equipmentSignals.ts), [frontend/app/utils/failEquipmentSignals.ts](frontend/app/utils/failEquipmentSignals.ts)
- Frontend: previous-window deltas on Recipe 현황 KPIs. — [frontend/app/utils/recipeStatusDelta.ts](frontend/app/utils/recipeStatusDelta.ts)
- Frontend: storage tiers (90/98). — [frontend/app/utils/storageUsage.ts](frontend/app/utils/storageUsage.ts)
- Frontend: alarm grouping by `(eqp_id, ppid)` and scope groups across recipe/tool/lot. — [frontend/app/utils/liveAlarm.ts](frontend/app/utils/liveAlarm.ts)
- Frontend: TTTM maximal cliques, MDS, PCA, tolerance scaling, tuning targets. — [frontend/app/utils/tttmGrouping.ts](frontend/app/utils/tttmGrouping.ts), [frontend/app/utils/fleetMap.ts](frontend/app/utils/fleetMap.ts), [frontend/app/utils/parameterPca.ts](frontend/app/utils/parameterPca.ts), [frontend/app/utils/tttmLimits.ts](frontend/app/utils/tttmLimits.ts), [frontend/app/utils/pmTuningTarget.ts](frontend/app/utils/pmTuningTarget.ts)
- Frontend: rule engine (cap resolution, mother/son inheritance, lot health traffic light) and its explanation. — [frontend/app/utils/ruleEngine.ts](frontend/app/utils/ruleEngine.ts), [frontend/app/utils/lotHealth.ts](frontend/app/utils/lotHealth.ts), [frontend/app/utils/ruleExplain.ts](frontend/app/utils/ruleExplain.ts)
- Frontend: hardware derived views — laser 3σ outliers, MDC change list and ppm deltas vs fleet median, SCE harmonics, sibling box plots. — [frontend/app/utils/fdcLaser.ts](frontend/app/utils/fdcLaser.ts), [frontend/app/utils/mdcHistory.ts](frontend/app/utils/mdcHistory.ts), [frontend/app/utils/sceCompare.ts](frontend/app/utils/sceCompare.ts), [frontend/app/utils/hardwareCompare.ts](frontend/app/utils/hardwareCompare.ts)
- Frontend: recipe configuration diff and coverage classes. — [frontend/app/utils/recipeCompare.ts](frontend/app/utils/recipeCompare.ts)
- The internal brainstorm states the same shape: showing is deep, questioning is shallow; missing are a comparison baseline, the reason/scope of a verdict, and support for the next decision. — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (요약 1)
- Cp/Cpk and pass/fail are excluded by decision because no process spec or target contract exists in the repo. — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§3 스큐보아, §4)
- TTTM's contract carries scalars only (no σ, n, quantiles or distributions), so variance-ratio and Wasserstein metrics cannot be computed on either side today. — [docs/research/tttm/tttm-page-implementation-review.md](docs/research/tttm/tttm-page-implementation-review.md) (§3 A-1, B-0)

### Inferences

- (inference) The "pure function in `utils/` + thin component" convention means most new analytics that reuse already-fetched data can be added without backend or office work; the plans doc makes this an explicit rule ("백엔드를 고치고 싶어지면 그 항목의 범위가 틀린 것입니다").
- (inference) Any analytic needing per-run distributions (TTTM variance/drift, TAT tails server-side) or history beyond the 60-day `meas_hist` retention requires new office-side computation or a rollup job, which the home environment cannot validate.

### Gaps

- Whether hardware panels compute control limits on their trends (beyond the laser 3σ outlier function) was not verified by full read.
- The exact formulas inside `backend/ebeam/recipe_tat/providers/_shape.py` and `fail_issue/providers/_shape.py` were not read; the descriptions above come from contract comments.

## 3. Thin versus analytic pages; what each lacks (trend, comparison, drill-down, export, thresholds, saved state)

### Takeaway

Thin: 장비 상태, 미연결 장비, 스토리지, Recipe 검색, 횡전개, 측정 이력. Analytic: Recipe 현황, H/W 관리, TTTM/PM 튜닝, 디바이스 통계/계측 룰, Recipe 비교 (configuration only), 라이브 알람 (short-window grouping). Time trend exists only on Recipe 현황, H/W 관리, TTTM and 디바이스 통계 (weekly); alerting/notification exists nowhere; URL-shareable state exists on only four page families.

### Cited Findings

Capability matrix (Y = evidence found, N = not found by grep, n/a = not applicable). "URL state" means the page reads `route.query`.

| Page | Time trend | Comparison | Drill-down | Export | Thresholds | Persisted state | URL state |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 장비 상태 | N | N | link to skewvoir search; H/W via store | Y | N | N | N |
| 미연결 장비 | N | N | N | Y | N | N | N |
| 스토리지 | N | N | N | N | Y (90/98) | N | N |
| Recipe 현황 (TAT/Fail) | Y daily | Y prev window, tool vs fleet, tool vs tool | recipe rows → recipe detail | Y | Y (OFFICE-VERIFY constants, CI) | N (date range is local) | `tab` only |
| Recipe 검색 | N | via compare cart | row → open/lateral/meas-hist/skewvoir | N | N | recent searches, working set | `q,page,size` |
| 열어보기 | N | N | parameter → settings/images | Y Excel | N | N | `recipe_name,fab_name` |
| Recipe 비교 | N | Y config diff | per-parameter detail | Y workbook | coverage classes | working set | N found |
| 횡전개 | N (version list only) | N | N | N | N | N | `recipe_name,fab_name` |
| 측정 이력 | N | N | MSR → skewvoir analysis | N | Y (15% fail) | N | `recipe_name,fab_name` |
| H/W 관리 | Y | Y sibling/fleet | time → recipes → 측정 이력 | partial (BSM, Sharpness) | laser 3σ; others unverified | chart axis range, theme | `eqp_id,start,end` (read once) |
| 라이브 알람 | N (20 min window) | N | recipe → recipe search; align images | N | n/a | filter | N |
| TTTM / PM 튜닝 | Y trend + epochs | Y pairwise | cell matrices | N | Y tolerance knob | settings per fab, panels | N |
| 디바이스 통계 | Y weekly | Y lot vs lot | lot → recipe → parameter | Y | Y rule caps, traffic light | fab, cart, presets, judgeSons | N |
| 채팅 | n/a | n/a | sources/figures | N | n/a | threads (server) | N |

- Export evidence: download helpers are imported in `ToolInventoryView`, `tool-roster`, `RecipeTatView`, `FailIssueView`, both equipment views, `RecipeCompareView`, `BsmPanel`, `SharpnessPanel`, `ComplianceTable`, `LotTable`, `LotDetailModal`, `device-statistics/index.vue`; `RecipeOpenView` has its own Excel download. Not found in `StorageView`, `LiveAlarmView`, `LabView`/`tttm/*`, `RecipeMeasHistView`, `RecipeLateralView`, FDC/MDC/SCE/Reso/BM-PM panels. — grep over [frontend/app/components/ebeam/](frontend/app/components/ebeam) and [frontend/app/pages/](frontend/app/pages)
- URL state evidence: `route.query` is read only in `HardwareView.vue`, `RecipeSearchView.vue`, `RecipeStatusView.vue`, `RecipeDetailNav.vue`, `RecipeSwitcher.vue`, `utils/recipeView.ts`, the fab/navigation composables and skewvoir. The brainstorm lists 스토리지, TTTM, 라이브 알람, 장비 상태, 디바이스 통계, Mag/Pixel as having no URL contract. — grep; [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§1.1)
- Persisted state evidence (`usePersistedState` callers outside skewvoir/AFM): device statistics preferences, cart presets, recipe recent searches, recipe selection set, TTTM settings, lab panels, live alarm filter, row-card view, chart theme, profile axis range, notices last-seen. — grep over [frontend/app/composables/](frontend/app/composables)
- Recipe 현황's date range is not persisted or in the URL (local `userDateRange`). — [docs/research/2026-10-06-page-value-plans.md](docs/research/2026-10-06-page-value-plans.md) (S3)
- 측정 이력 shows one aggregate line only; per-tool P50/P90 tails (S4) are planned but no `measHistTails`/`equipmentTails` exists in the tree. — [docs/research/2026-10-06-page-value-plans.md](docs/research/2026-10-06-page-value-plans.md) (S4); grep returned nothing
- No notification/alerting channel exists on any page: the only real-time surface is the live alarm board, which is collected only while someone is viewing and pruned after 30 minutes. — [backend/ebeam/live_alarm/contracts.py](backend/ebeam/live_alarm/contracts.py); [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§3 라이브 알람, §4)

### Inferences

- (inference) The thin pages are thin because their office source is a current snapshot with no history (sem_list roster, storage collector, idp_ver current version), not because analysis was skipped; adding trend to them needs new collection, which the owner has so far declined for storage.
- (inference) Export is uneven within one page family: on H/W 관리 only two of seven panels export, and the three pages a shift engineer would most want to hand over from (라이브 알람, 측정 이력, TTTM) have no export at all.
- (inference) Because most pages keep filters in memory or localStorage rather than the URL, a finding on those pages cannot be shared as a link. Only recipe detail, recipe search, H/W 관리 and Recipe 현황's tab can.

### Gaps

- The matrix cells marked N are "not found by the grep patterns used", not proofs of absence; a control case was run for exports and `route.query`, but not for every column.
- Whether H/W 관리 writes its tool/window back into the URL as the user changes them (it reads them once) was not verified.

## 4. How pages connect: navigation grouping, shared scope, links, hidden/lab pages

### Takeaway

Pages share scope through the URL (tool family, fab segment) and a navigation store, and connect through a small set of builder-made links centred on recipe identity (`full_name` + `fab_name`) and MSR identity. Navigation groups pages by URL shape rather than meaning; an accepted ADR (0006) defines a regrouping by domain and object that has not been executed.

### Cited Findings

- Feature tab row (in order): `장비 상태`, `Recipe 현황`, `Recipe 검색`, `H/W 관리`, `디바이스 통계` (cd-sem only), `스큐보아`. A `TTTM` tab entry is commented out. — [frontend/app/components/nav/FeatureTabs.vue](frontend/app/components/nav/FeatureTabs.vue)
- 장비 상태 has sub-tabs `장비 리스트` and `스토리지`. — [frontend/app/components/ebeam/EquipmentStatusSubTabs.vue](frontend/app/components/ebeam/EquipmentStatusSubTabs.vue)
- Header menus: 실험실 (`lab`) = `Mag/Pixel 가이드`, `라이브 알람`, `장비간 스큐(TTTM)`, `채팅`; App 정보 (`account`) = `공지사항`, `앱 소개`, `API 리스트`, `사용 통계`, `세팅`. The lab menu is not drawn on the landing hub before a tool is chosen. — [frontend/app/utils/headerNav.ts](frontend/app/utils/headerNav.ts)
- No lab/cloud visibility flag remains for e-beam pages: `hiddenOnCloud` was removed when TTTM went live on 2026-09-01. AFM visibility is a separate global middleware keyed on `AFM_ENABLED`. — [docs/adr/0006-page-grouping-by-domain-and-object.md](docs/adr/0006-page-grouping-by-domain-and-object.md), [frontend/app/middleware/afm-hidden.global.ts](frontend/app/middleware/afm-hidden.global.ts)
- ADR 0006 (accepted as a model, 2026-08-28; execution deferred until VeritySEM/Provision onboarding): top level splits by domain (E-Beam / 스큐보아 / AFM / Thickness); inside E-Beam seven tabs in three groups — 장비 (장비 상태 with sub-tabs 장비 리스트·스토리지·H/W 관리·미연결 장비; 라이브 알람; 장비 튜닝 BETA = TTTM·PM 플래닝), 레시피 (Recipe 현황; Recipe 검색), 측정 (측정 이력; 디바이스 통계). It lists the symptoms of the current grouping: a production monitoring board labelled 실험실, tab order 장비 → 레시피 → 레시피 → 장비 → 측정 → 측정, etc. — [docs/adr/0006-page-grouping-by-domain-and-object.md](docs/adr/0006-page-grouping-by-domain-and-object.md)
- Page identity for usage counting: rules for `/recipe-search/meas-hist`, `/recipe-search`, `/device-statistics`, `/recipe-status` (split by `tab`), `/storage`, `/hardware`, `/live-alarm`, `/tttm`, `/pm-planning` (+ alias `/pm-tune`), `/skewvoir`, `#tool-inventory`, and standalone `/tool-roster` (alias `/sem-list`), `/mag-pixel`, `/chat`. Ops pages (`/activity`, `/admin`, `/settings`, `/endpoints`, `/identify`, `/intro`, `/notices`) are never ranked. Identity is prefixed by tool family for e-beam pages. — [frontend/app/utils/pageIdentity.ts](frontend/app/utils/pageIdentity.ts)
- Shared scope: fab selection lives in the navigation store and the `[fab]` URL segment (multi-fab allowed); `fab_name` is the filter grain, while device statistics keeps its own `fac_id`-grained fab that "must never be written into the fab_name-grained store". — [frontend/app/utils/features.ts](frontend/app/utils/features.ts), [frontend/app/stores/navigation.ts](frontend/app/stores/navigation.ts)
- Existing links between pages:
  - 장비 상태 row → skewvoir search (`skewvoirSearchRoute`). — [frontend/app/components/ebeam/ToolInventoryView.vue](frontend/app/components/ebeam/ToolInventoryView.vue)
  - 장비 상태 row → H/W 관리 via `setSelectedTool` (shared state, not a URL). — [frontend/app/components/ebeam/ToolInventoryView.vue](frontend/app/components/ebeam/ToolInventoryView.vue)
  - Recipe rows (search, TAT/fail rankings) → 열어보기 / 횡전개 / 측정 이력 via `recipeDetailRoute`, and → skewvoir search. — [frontend/app/utils/recipeView.ts](frontend/app/utils/recipeView.ts), [frontend/app/components/ebeam/RecipeRowActions.vue](frontend/app/components/ebeam/RecipeRowActions.vue)
  - 측정 이력 row → skewvoir analysis (exact MSR). — [frontend/app/utils/skewvoirLinks.ts](frontend/app/utils/skewvoirLinks.ts)
  - H/W 관리 time pick → recipes in window → 측정 이력. — [frontend/app/components/ebeam/hardware/RecipeWindowSlideover.vue](frontend/app/components/ebeam/hardware/RecipeWindowSlideover.vue)
  - 라이브 알람 recipe → Recipe 검색 with a hand-assembled path. — [frontend/app/components/live-alarm/AlarmRow.vue](frontend/app/components/live-alarm/AlarmRow.vue)
  - Home → `/tool-roster`. — [frontend/app/pages/index.vue](frontend/app/pages/index.vue)
- Backend cross-feature dependencies: the TTTM page joins `tttm/check` with `pm-planning/fleet` by `eqp_id`; pm_planning, storage and tttm lean on sem_list for their roster; recipe_tat and fail_issue share one measurement universe; chat's data tools wrap recipe_tat and fail_issue `data.py` functions. — [backend/ebeam/pm_planning/providers/mock.py](backend/ebeam/pm_planning/providers/mock.py), [backend/ebeam/fail_issue/providers/mock.py](backend/ebeam/fail_issue/providers/mock.py), [backend/chat/data_tools.py](backend/chat/data_tools.py); [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§1.2 item 5)
- Link policy agreed 2026-10-05: a link is made only if (1) the target owns a URL entry contract, (2) the source holds the identifier without guessing (non-canonical values go only as an editable search term), (3) the link is built by a pure function owned by the target and the caller mutates no global state. Under it: three new links (S2, S16, S17), one link to fix (장비 상태 → H/W), and no tool hub, no home briefing, no filter links into pages without an entry contract, no AFM↔SEM links. — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§1.3–1.5)
- Identifier hazards recorded there: TAT/fail `recipe_name` differs from the class-qualified `full_name`; alarm `recipe_id`/`ppid` is not proven equal to `full_name`; device statistics `recipe_id` equals `full_name`; `eqp_id` is not unique without fab scope in the sem_list mock (10 duplicate ids in 304 rows). — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§1.2)

### Inferences

- (inference) The connective tissue between pages today is recipe-centric and MSR-centric; there is no tool-centric path that carries a tool plus a time window from an anomaly on one page (alarm, slow tool badge, storage warning, TTTM outlier) into another, except H/W 관리's own slide-over.
- (inference) TTTM, 라이브 알람, 스토리지 and 디바이스 통계 are link dead-ends in both directions under the current policy because they expose no URL entry contract; any opportunity that deep-links into them must first add such a contract and justify its maintenance.
- (inference) The ADR 0006 regrouping would change where pages sit but not what they compute; a report should not present "regroup navigation" as new, and should note it is waiting on VeritySEM/Provision onboarding.

### Gaps

- `FabSidebar.vue`, `LabMenu.vue`, `AppHeader.vue` and the layouts were not read; behaviour such as how the remembered tool/fab resolves dynamic lab links is taken from comments in `headerNav.ts`.
- `/intro` (816 lines) describes the app to users with its own five-way classification per ADR 0006; it was not read.

## 5. What the internal research docs already concluded; shipped, pending and rejected proposals

### Takeaway

The 2026-10-05 brainstorm and 2026-10-06 plans agreed nine page-value items plus five companions. As of 2026-10-09, four have shipped (S2, S5, S1, S3 — all on 2026-10-06); S4, S7, S13, S8, S6, S17, S16, S10, S11 and the 장비 상태 → H/W link fix have not. A long explicit "do not build" list exists and must not be re-proposed without new grounds.

### Cited Findings

- Diagnosis: pages are deep at "showing" and shallow at "questioning" — no comparison baseline (statistics move with the selection), no stated reason/scope for a verdict, no support for the next decision. — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (요약 1)
- Agreed items, in the brainstorm's rank order: S3 Recipe 현황 previous-period delta; S4 측정 이력 per-tool P50/P90 and slow-run separation; S5 계측 룰 verdict explanation; S2 측정 이력 row → skewvoir; S1 라이브 알람 incident scope; S6 AFM fixed baseline; S7 skewvoir base/target comparison; S13 계측 룰 unsaved cap what-if; S8 skewvoir review receipt. Companions: S10 storage two observation times, S11 TTTM production-recipe overlap, S16 device statistics step → 열어보기, S17 alarm → skewvoir search, 장비 상태 → H/W link replacement. Next large task: S9 H/W before/after maintenance comparison. — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§2), [docs/research/2026-10-06-page-value-plans.md](docs/research/2026-10-06-page-value-plans.md)
- Shipped (git log, all 2026-10-06): S2 `edb5c692` "link each row's MSR to the skewvoir analysis"; S5 `3b53d1d8` "explain why each recipe was judged against its cap"; S1 `aba5774b` "group the board by recipe, tool and lot scope"; S3 `e382e300` "show each KPI's change against the previous same-length window"; follow-up review fixes `415722bc`, `13b29c40`, `8e191ca8`, `3d716b38`. — `git log --oneline -150`
- Not shipped (verified by grep on 2026-10-09): S4 (no `measHistTails`/`equipmentTails`); S17 (no `skewvoirSearchRoute` in `components/live-alarm`); S7 (no `baselineCompare`); S13 (no `ruleWhatIf`/`applyCapDraft`); S8 (no `buildReviewReceipt`); S10 (`rcp_counts_mt` appears only in the type at [frontend/app/composables/useStorageApi.ts](frontend/app/composables/useStorageApi.ts)); S11 (`production_corroboration` appears only in [frontend/app/composables/useTttmApi.ts](frontend/app/composables/useTttmApi.ts)); S16 (no link in [frontend/app/components/cdsem/comparison/StepOutlierCard.vue](frontend/app/components/cdsem/comparison/StepOutlierCard.vue)); H/W link fix (`setSelectedTool` still called in [frontend/app/components/ebeam/ToolInventoryView.vue](frontend/app/components/ebeam/ToolInventoryView.vue), no `hardwareRoute`).
- Since 2026-10-06 the commit stream is almost entirely AFM (office adapter, tips, usage, recipes pages), plus three H/W fixes and activity/visitors work; no further e-beam page-value item landed. — `git log --oneline -150`
- The plans doc's own caveats: the list was chosen by two models reading code only — "사용 로그도, 엔지니어 인터뷰도 근거에 없습니다"; all nine items re-compute already-fetched data and create no new facts; the intended check after batch 1 is `/activity` per-feature counts plus three direct questions to engineers. — [docs/research/2026-10-06-page-value-plans.md](docs/research/2026-10-06-page-value-plans.md) (요약, 확인 방법)
- Per-page "candidate" (not adopted, single-feature) ideas already on record: home data-availability indicator; 장비 상태 version distribution per model and minority-version tools, connected/unconnected ratio per FAB × model; Recipe 현황 representative runs for a selected cell; 열어보기 configuration consistency check (S14); 측정 이력 grouping probable retries; Recipe 비교 classifying differences (acquisition/addressing/geometry/reporting); 디바이스 통계 weekly change decomposition; Mag/Pixel alternatives comparison; intro investigation-path examples. — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§3)
- "Held" ideas (need a cross-feature join or office confirmation): unreachable tools' recent measurement exposure; storage exhaustion date; storage warning queue with recent runs; Recipe 현황 change decomposition and movers list (after S3); TAT × fail joint queue (S19); Recipe 검색 result rows with recent run stats; setting-equivalence grouping; mother/son run budget; planned vs observed positions; H/W affected-run list for an anomaly window; H/W planned vs actual maintenance duration; TTTM pair evidence check, group robustness, post-PM evidence closure; device statistics excess-measurement work list (S20) and R&D → production comparison via `rnd_connector`; chat combined report from an evidence bundle (S18). — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§3)
- Rejected / will not build: tool summary hub; home briefing and watch list; fleet health score and H/W scoreboard; "saved time" estimate and equipment utilisation; alarm shift summary, acknowledge/resolve flow, chronic badge; attributing past results to recipe versions; storage forecasting collector (for now); Cp/Cpk and personal "official baselines"; point sampling (user decision 2026-10-06); AFM ↔ SEM ↔ Thickness auto-linking; new OpenSearch index or mapping changes; automatic recipe deployment / MDC adjustment / disk deletion; mobile or laptop layouts; event markers on Recipe 현황 trends (S9 answers it from the H/W side); per-version fail/TAT on 횡전개; substitute-tool evidence table. — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§3, §4)
- TTTM research conclusions: "machine learning" is the wrong tool (the question is variance decomposition/state-space estimation, no labels exist); the first thing to build is a nightly run-grain rollup because `dict_pkl` expires at 61 days and `meas_hist` at 60; the best home task is a generative mock with known true values; order is skewvoir lens → rollup → filter → fleet page. — [docs/research/2026-08-16-skew-tttm-feasibility.md](docs/research/2026-08-16-skew-tttm-feasibility.md) (요약, §9)
- TTTM page review: MDS fleet map done 2026-08-16; tolerance ceiling stays 0.20 nm ("다시 제기하지 마십시오"); remaining frontend-only items are an ABBA uncertainty floor line and per-cell sample-count warning, a carryover footnote, and using unused data (epoch marker labels, `mdc_epoch`); distribution statistics in the contract (B-0) are a precondition for variance-ratio/Wasserstein metrics, DBSCAN consensus, mixed-effect RCA and continuous drift monitoring; contour matching and virtual metrology are long-term, office-dependent. — [docs/research/tttm/tttm-page-implementation-review.md](docs/research/tttm/tttm-page-implementation-review.md)
- ADR 0005 defines a two-mode point-sampling recommendation engine, but point sampling was removed from the current scope by user decision on 2026-10-06. — [docs/adr/0005-metrology-sampling-two-mode-engine.md](docs/adr/0005-metrology-sampling-two-mode-engine.md), [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§4)
- Open issue sets in `.scratch/`: `skewvoir-msr-review` (nine tickets on trustworthy MSR review detection, mostly open — skewvoir scope), `skewvoir-annotation` (per-MSR annotation, needs triage), `fdc-fleet-view`, `sk-bad-sweep`, `mock-office-drift` (nine tickets, done except one deferred), AFM review/scale sets. — [.scratch/](.scratch)
- A pending office request exists for Recipe 현황: "ask the office scheduler for an hourly pre-aggregated cube" (2026-10-04). — commit `1ab073fb`

### Inferences

- (inference) The unshipped S-items are already designed down to file and function names, so they are "ready work", not new ideas; a final report should present them as an existing backlog and spend its novelty elsewhere.
- (inference) The rejections cluster around three reasons — new collection state, cross-feature coupling in one component, and claims the data cannot support. Any new opportunity that needs history (storage forecast, alarm history, post-PM persistence) has to argue against the first reason explicitly, and the brainstorm itself notes history "cannot be created retroactively".
- (inference) The TTTM nightly rollup is the one place where the internal research itself says a new stored dataset is necessary; whether it has been built is not visible from the frontend or contracts read here.

### Gaps

- Whether the nightly TTTM rollup job exists in `backend/_scheduler/` was not checked.
- `docs/issues/ground_rules/` (grilling log D12/D17/D18/D22, rule editor structure), `docs/opencode/` debate records and `docs/afm/` were not read.
- `.scratch/fdc-fleet-view` and `.scratch/sk-bad-sweep` ticket contents were only listed, not read.
- DESIGN.md (701 lines) was not read beyond references to it; visual-language constraints (`--sk-*` tokens, tab count limit of 4–7 cited in ADR 0006) are taken second-hand.

## 6. Usage signal: what the activity/visitors feature records, and whether the repo shows which pages are used

### Takeaway

The app records page opens per page identity and per tool family and exposes rankings at `/activity` and `/admin/visitors`, but the repository contains no real usage numbers — at home the reader is a mock, and the planning docs state that no usage logs informed the priorities.

### Cited Findings

- Endpoints: `/api/activity/me`, `/summary`, `/fabs`, `/families`, `/users`, `/visitors`, `/users/<user_id>`, and beacons `POST /api/page-view` and `POST /api/page-view/<family>`. — [backend/activity/routes.py](backend/activity/routes.py)
- `SummaryResponse` = `dau, wau, mau, top_features_7d, top_features_30d`; `FabUsageResponse` (per fab, counted from requests because beacons carry no fab); `FamilyUsageResponse` (distinct people and page counts per family `cdsem | hvsem | veritysem | provision | afm`, from `page_view` rows); `VisitorsResponse` (daily visitors with rolling WAU/MAU); per-user `daily`, `visits`, `recent_features`, `first_seen`, `last_seen`. — [backend/activity/contracts.py](backend/activity/contracts.py)
- Page-to-feature slugs used for ranking: `meas_hist`, `recipe_search`, `device_statistics`, `skewvoir`, `storage`, `hardware`, `live_alarm`, `skew_check` (the tttm page; slug kept after the rename), `pm_planning`, `recipe_tat`, `fail_issue` (recipe-status tabs `align` and `meas` both map to `fail_issue` but count as separate opens), `sem_list` (`/tool-roster`), `mag_pixel`, `chat`, `afm` (+ `afm_tips`, `afm_usage`, `afm_recipes`). — [backend/_logging/feature_map.py](backend/_logging/feature_map.py), [frontend/app/utils/pageIdentity.ts](frontend/app/utils/pageIdentity.ts)
- Granularity limits: the beacon fires per page identity, so a fab switch or filter change is not a new open; landing on 장비 상태 from the hub is treated as a waypoint and not counted; the tool family rides in the beacon URL and no index field was added. — [frontend/app/utils/pageIdentity.ts](frontend/app/utils/pageIdentity.ts)
- Sub-feature usage (which block on a page was looked at) is not recorded and will not be: "하위 기능별 비콘은 인덱스 변경이 필요하므로 만들지 않습니다." — [docs/research/2026-10-06-page-value-plans.md](docs/research/2026-10-06-page-value-plans.md) (확인 방법)
- The home activity provider is "Network-free activity aggregation for home and automated tests"; real rows live in the office OpenSearch logging index. — [backend/activity/providers/mock.py](backend/activity/providers/mock.py)
- The only usage-related statement about engineers found in the docs is an unsourced assertion that the live alarm board is "교대 근무자가 가장 많이 쓰는 화면". — [docs/research/2026-10-05-page-value-brainstorm.md](docs/research/2026-10-05-page-value-brainstorm.md) (§3 라이브 알람)
- Recent work extended the usage views themselves: `/admin/visitors` with DAU/WAU/MAU tabs (2026-10-08), page usage per tool family (2026-10-02), AFM tabs ranked as their own pages (2026-10-08). — commits `609c99de`, `f4572b81`, `6074f9a6`

### Inferences

- (inference) Real per-page ranking exists only at the office (`/activity` → `top_features_7d/30d`, `/activity/families`). Reading those numbers there is the cheapest available evidence for prioritising pages and requires no code change.
- (inference) Because fab is not in the beacon and sub-page blocks are not tracked, usage data can rank pages and tool families but cannot say which fab's engineers use a page or whether the four shipped S-items are being looked at.

### Gaps

- No real usage counts, rankings or user interviews were found anywhere in the repo (searched `docs/` for usage figures; only design specs and plans matched). Which e-beam pages engineers actually use most is unknown from this source.
- `/activity` and `/admin/visitors` page components were only grepped for labels; exactly which rankings they render was not verified by full read.
