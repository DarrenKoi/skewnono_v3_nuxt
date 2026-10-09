# Skewvoir (스큐보아) current state — codebase inventory as of 2026-10-09

Source is the local repository `/Users/daeyoung/Codes/skewnono_v3_nuxt` only; no web sources were used. Every citation is a repo-relative path with line numbers.

Path abbreviations used below:

- `FE/` = `frontend/app/`
- `SK/` = `frontend/app/components/ebeam/skewvoir/`
- `UA/` = `frontend/app/utils/skewvoirAnalysis/`
- `BE/` = `backend/`
- `PKL` = `docs/datatables/hitachi/msr_file_pickle.txt`
- `MH` = `docs/datatables/hitachi/meas_hist.txt`
- `FTP` = `docs/datatables/hitachi/msr_image_ftp.txt`

How this was verified: I read directly `SearchLanding.vue`, `Workspace.vue`, `workspace/LeftRail.vue`, `views/Dashboard.vue`, `views/PositionStack.vue`, `views/Fdc.vue`, `useSkewvoirWorkspace.ts`, `useSkewvoirRoute.ts`, `UA/types.ts`, `UA/routeQuery.ts`, the three `contracts.py`, and `docs/issues/skewvoir/analysis-coverage-gap-analysis.md`. The remaining ~20k lines were read by four delegated read-only passes; I spot-checked their load-bearing claims by grep (ProvenanceDrawer unmounted, no caller for bulk download, no crosshair in skewvoir, `anomalyCfg` wiring, FDC key spellings, `focusError` consumers, no view beacon). Line numbers from the delegated passes were not individually re-opened. Nothing was run in a browser, so all behaviour claims are from reading code.

Labels: **(a)** = exists today, **(b)** = data exists but is unused, **(c)** = inferred gap/opportunity. Anything under "Inferences" is inference, not fact.

## 1. What is skewvoir for, and what is the engineer's workflow?

### Takeaway

Skewvoir is a two-route tool: a cross-fab measurement search landing, and a six-view analysis workspace whose whole state lives in the URL. It answers "what is unusual inside the measurement(s) I picked" for Hitachi CD-SEM / HV-SEM only; it has no fixed reference, no spec, and no way to record a conclusion.

### Cited Findings

**Purpose as documented**

- "개별 측정 결과, 장비 상태, 측정 실행 및 데이터 품질 정보를 연결하여 검토가 필요한 측정을 빠르게 식별하고 원인을 분석" — `docs/project-overview.md:76-78`.
- Two modes are defined: single MSR ("이 측정은 유효하며, 웨이퍼 안에서 어디가 다르고, 측정 중 장비 신호는 어떻게 움직였는가?") and multi MSR ("비교 가능한 측정들 사이에서 무엇이 이동·확산·변화했고…") — `docs/issues/skewvoir/wafer-analysis-method-research.md:13-20`.
- The owner's own October summary: 지금 = "고른 측정 안에서 무엇이 특이한지, 위치·FDC·시계열·상관·이미지로 봅니다."; 빠진 것 = "고정된 기준에 비해 얼마나 움직였는지, 결론을 어떻게 남기는지, 포인트를 줄여도 되는지." — `docs/research/2026-10-05-page-value-brainstorm.md:438-440`.
- Division of labour with TTTM: skewvoir answers size ("이 비교에서 얼마나 벌어져 있는가", user-picked set, tens of measurements), the TTTM page answers whether it reproduces — `docs/research/2026-08-16-skew-tttm-feasibility.md:305-318`.

**Routes and registration (a)**

- Four pages, each a thin wrapper: `FE/pages/ebeam/{cd-sem,hv-sem}/skewvoir/index.vue` (→ `SearchLanding`) and `analysis.vue` (→ `Workspace`); both set `hideFabSidebar` and `lockDesktopPageScroll`.
- Registered for `cd-sem` and `hv-sem` only — `FE/utils/features.ts:68`; tab in `FE/components/nav/FeatureTabs.vue:38`. No lab/hidden flag exists.
- The route's tool type keys the session (selection, recents) but does **not** narrow the search; search spans both SEM indices unless the 카테고리 filter picks exactly one — `SK/SearchLanding.vue:128-132`, `FE/composables/useMeasHistSearch.ts:200-207`.

**Search landing (a)**

- Layout: search bar + filter bar + scope strip | selection workbench, over a result table, with a 340px recently-viewed rail — `SK/SearchLanding.vue:1-80`.
- Query grammar: tokens split on whitespace/comma/semicolon; prefixes `lot|recipe|eq|msr|date|q:`; unprefixed tokens are classified date → MSR → EQ (exact facet match) → LOT (regex) → free text — `FE/utils/measHistQuery.ts:41-133`. Chips show how each token was read — `SK/search/SearchBar.vue:46-71`. `q:` is not in the help popover — `SK/search/SearchScopeStrip.vue:23-29`.
- Filters: FAB → 카테고리 → 장비 모델 → EQ cascade, multi-select with counts; there is no recipe facet — `SK/search/FilterBar.vue:8-36`, `FE/composables/useMeasHistApi.ts:65-68`.
- Date range defaults to `anchor − retention_days … anchor` (anchor is the backend's newest timestamp, not wall clock; retention 60 days) — `FE/composables/useMeasHistSearch.ts:98-101`, `FE/composables/useMeasHistFacets.ts:20,38-39`. Presets 7 / 30 / retention — `SK/search/FilterBar.vue:97-104`.
- Result table columns: checkbox, LOT, RECIPE (`full_name`, copy button), EQ, FAB, CAPTURED — `SK/search/ResultTable.vue:216-254,325-331`. Page size 50 with "더 보기"; hard cap 10,000 — `FE/composables/useMeasHistSearch.ts:50,176`.
- Sorting is client-side over loaded rows only (timestamp, recipe, eq, lot); a "불러온 N건만 정렬했습니다" notice appears when more pages exist — `FE/composables/useMeasHistSearch.ts:300-313`, `SK/search/ResultTable.vue:265-270`.
- Clicks to a result: single = type, Enter, one row click → Dashboard. Set = N checkboxes (or header select-all) + one "Time-Series" button → Time-Series view — `SK/SearchLanding.vue:162-173`.
- The selection workbench's only action is "Time-Series"; a set always opens on that view — `SK/search/SelectionWorkbench.vue:23-31`, `SK/SearchLanding.vue:172`.
- Selection has no hard cap in search, but analysis keeps only the first 30 (`TREND_LIMIT = 30`) — `UA/curatedSet.ts:17,100-107`; the workbench only notes "최대 30개 표시" — `SK/search/SelectionWorkbench.vue:19-22`.
- Recently viewed: max 15 entries, single or time-series set, expiry judged against the backend anchor — `FE/composables/useSkewvoirRecentlyViewed.ts:19-21,49-66`.

**Workspace shell (a)**

- 240px left rail (back-to-search button, six view modes with keys 1–6, SELECTION block, ACTIONS) plus one view body — `SK/Workspace.vue:1-83,177-185`, `SK/workspace/LeftRail.vue:1-239`.
- Six views — `FE/composables/useSkewvoirWorkspace.ts:36-43`: 측정 개요 (`dashboard`), 위치 비교 (`position-stack`), FDC 분석 (`fdc`), Time-Series, 상관 / 분포 (`correlation`), 이미지 갤러리 (`gallery`).
- Scope is `single` or `set`; each view branches on it. A member row in the rail is clickable to move focus only on views that draw one measurement and only for a set — `SK/workspace/LeftRail.vue:262-270`.
- Rail actions: 요약 복사, Recipe 열어보기 (opens recipe detail in a new tab, disabled without a meas_hist row), Share (short link `/s/<code>` with long-URL fallback), MSR 원본 받기, Pickle 받기 (focus MSR only; 410 = past retention) — `SK/workspace/LeftRail.vue:399-524`.
- 분석 준비 상태 modal: compatibility groups, excluded MSRs with reasons, three capability rows — `SK/workspace/ReadinessModal.vue:40-126`. 상세 보기 modal includes the set editor — `SK/workspace/SelectionDetailModal.vue:76-97`.

**URL state (a)**

- URL query is the single source of truth: `lot, recipe, eq, mp, msr, msrs, cap, view, scope` plus `site, ref, metric, grain, fdcaxis, tsview, tsx, tsb, x, y, filter` — `UA/routeQuery.ts:84-204`, `FE/composables/useSkewvoirRoute.ts:45-83`.
- Defaults are omitted from the URL by rule — `UA/routeQuery.ts:135-180`.
- View switches use `router.replace`, so Back returns to search — `FE/composables/useSkewvoirRoute.ts:97-100`.
- `ref`, `metric`, `grain` are parsed and preserved but described as "opaque passthrough strings for now" with consumers in "later tasks" — `FE/composables/useSkewvoirRoute.ts:61-67`.

**Entry points from other pages (a)**

- To the landing with `?q=…&fab=…` (consumed once, then stripped): 장비 리스트 (`FE/components/ebeam/ToolInventoryView.vue:152-160`, `eq:`), Recipe 검색 (`RecipeSearchView.vue:939-946`, `recipe:`), recipe row actions (`RecipeRowActions.vue:37-66`), recipe detail nav (`RecipeDetailNav.vue:65-74`).
- Directly to analysis: 측정 이력 row "열기" — `FE/components/ebeam/RecipeMeasHistView.vue:321-330` (shipped 2026-10-06, commit `edb5c692`).
- Route builders live in `FE/utils/skewvoirLinks.ts:28-56`.

### Inferences

- (c) The set workflow is Time-Series-first by construction; an engineer who wants a set-scope position, FDC or correlation reading must open Time-Series and then switch view.
- (c) Because search does not cap selection but analysis silently keeps 30, a 40-row selection loses 10 members with only a small note on the landing.
- (c) There is no path from a finding back out to a fixed record: sharing is a live re-query link, and pickles expire at 61 days, so a shared link eventually stops reproducing.

### Gaps

- No usage evidence exists. The planning doc says so directly: "사용 로그도, 엔지니어 인터뷰도 근거에 없습니다" — `docs/research/2026-10-06-page-value-plans.md:27-29`. A per-view beacon was designed (`docs/superpowers/specs/2026-08-04-skewvoir-view-usage-design.md`) but no code for it exists (grep for `skewvoir/view` and `ViewBeacon` in `FE/` and `BE/` is empty). Page-level logging treats all of skewvoir as one identity — `FE/utils/pageIdentity.ts:96`.
- I did not load the pages in a browser, so actual click counts, render times and layout at 1920×1080 are unverified.

## 2. Which backend features feed it, and what do they expose?

### Takeaway

Three Hitachi-only features feed it: `meas_hist` (one row per recipe run), `msr_file` (one parsed pickle per MSR = one wafer, one row per measurement, plus per-sequence FDC), and `msr_image` (images fetched from the tool FTP). There is no spec, target, control limit, per-sequence timestamp, or slot field anywhere in these sources, and the mock's CD↔FDC relationship is fabricated.

### Cited Findings

**Endpoints (a)**

| Endpoint | Limits | Called by skewvoir |
| --- | --- | --- |
| `GET /api/meas-hist/search` | `limit` ≤ 500, window ≤ 10,000 (`BE/meas_hist/providers/mock.py:526-527,714-718`) | yes, page size 50 |
| `GET /api/meas-hist/facets` | terms size 1000 (`BE/meas_hist/providers/office_example.py:120`) | yes |
| `GET /api/meas-hist` | last 30 days (`mock.py:523`) | yes (`FE/composables/useSkewvoirAnalysis.ts:62,82`) |
| `GET /api/meas-hist/window` (eqp_id + time ±30 min) | size 200 (`BE/meas_hist/routes.py:99-117`) | **no** — only `FE/components/ebeam/hardware/RecipeWindowSlideover.vue:150` |
| `GET /api/msr-file` | — | yes (focus) |
| `POST /api/msr-files` | `MAX_BULK = 200` (`BE/msr_file/routes.py:16`) | yes (set) |
| `GET /api/msr-file/download` | 404 / 410 distinguished (`BE/msr_file/contracts.py:181-194`) | yes (rail) |
| `POST /api/msr-files/download` (zip, ≤100) | `BE/msr_file/routes.py:134-197` | **no caller** (only `FE/data/apiCatalog.ts:522`) |
| `GET /api/msr-image` | `preview=1` WebP, cond sidecar in `X-Msr-Cond` header (`BE/msr_image/routes.py:139-223`) | yes |
| `POST /api/msr-images` + `GET /api/msr-images/<job>` | ≤500 names, max 2 running jobs (`routes.py:269,296-297`) | yes, as cache warmer only |
| `GET /api/msr-images` (list) | — | **no caller** |

- Rate limit: `/api/*` is 50 req / 5 s per user; `msr_image` is exempt, `msr_file` and `meas_hist` are not — `BE/__init__.py:79,101`.

**Grain**

- One `meas_hist` row = one tool running one recipe on one lot once; `id = msr` — `MH:2,10`.
- One MSR = one pickle with one `exe_detail_info` (one `wafer_id`, one wafer map) — `PKL:201-213`.
- One `MsrFileRow` = one measurement = one `sequence` (a global running counter across parameters) — `PKL:35-41` (office 확인 2026-07-27).
- `len(df_result_data) == len(dynamic_fdc)` — `PKL:288-292` (office 확인 2026-07-27).
- Rows with `parameter == ""` are unnamed settling shots with real CD and image — `PKL:46-51`.
- Images: CD-SEM usually one per row; HV-SEM several with `-U/-T/-M/-L` suffixes — `PKL:175-180` (user-confirmed 2026-08-08).
- Real volume: 2,250,652 meas_hist documents — `MH:40` (office 확인 2026-08-20).

**Contract fields** (definitions: `BE/msr_file/contracts.py:31-160`, `BE/meas_hist/contracts.py:20-45`)

- `MsrFileRow`: `sequence, chip_number, chip_coordinate, stage_coordinate, dnum_group, mp_number, parameter, cd_value (nullable), no_of_mp_image, mp_image_name_01, mp_image_names, meas_condition_mag/vac/pixel, addressing1_score, addressing2_score, measurement_score, meas_method, object_type, meas_kind`.
- `MsrFileResponse`: `eqp_ip, total_images, sequence_count, health, parameters[] (count/mean/std/min/max/unit), fdc_params[] (nominal/mean/std/min/max/drift_sigma/status), fixed_fdc, dynamic_fdc, exe_detail_info, alignment, spm_dict, rows`.
- `MeasHistRow`: `fac_id, fab_name, vendor_nm, eqp_id, eqp_ip, eqp_model_cd, tool_type, lot_cd, lot_id, class_name, recipe_name, full_name, timestamp, start_time, end_time, meastime, msr, msr_check, align_fail, total_images, fail_images, fail_ratio (percent), idp_name, idw_name`.

**Units and conventions**

- `cd_value`: no unit column in the pickle; nm assumed (user-confirmed 2026-08-08) — `PKL:83-85`. Unit is derived from the parameter name by substring — `BE/msr_file/providers/mock.py:390-420`.
- `stage_coordinate` is nm; `chip_number` is a die index; `wafer_size`, `chip_pitch`, `map_offset` are nm; `map_origin` is a die index — `PKL:42-43,209-213`.
- `chip_coordinate` is **absent from the real pickle**; the office adapter emits `""` — `PKL:398-400`, `BE/msr_file/providers/office_example.py:322-325`.
- `meas_condition_vac` is acceleration voltage in V and the only beam attribute in the pickle — `PKL:190,482-485`.
- Pixel size derivation `FOV_µm = 135000 / Mag` — `docs/datatables/hitachi/mag_pixel.txt:55-58` (constant is OFFICE-VERIFY).
- Real `fixed_fdc` has 29 keys and real `dynamic_fdc` 39 keys, with no documented units or nominals — `PKL:249-277,298-336`. The mock models 7 and 12 respectively — `BE/msr_file/providers/mock.py:462-493`.

**Backend-side statistics (a)**

- Per-parameter summary: count, mean, sample std, min, max — `BE/msr_file/providers/mock.py:1076-1108` (shared with office).
- FDC summary: mean, population std, `drift_sigma = |mean − nominal| / sigma`; status `bad` ≥ 3.5, `warning` ≥ 2.0 — `mock.py:447-459,629-637,1056-1071`.

**What is fabricated or absent**

- `health` is a mock seed that drives FDC drift, CD mean shift and quality scores together, so CD↔FDC correlation at home is generator-made — `BE/msr_file/providers/mock.py:27-29,622-623,707,1039-1052`; `BE/msr_file/MIGRATION.md:73-76`.
- `spm_dict` is one 32-point profile per MSR (not per point); the mock is a placeholder — `PKL:352-356`, `mock.py:214-221`.
- No per-sequence timestamp — `PKL:401-404`. No spec/target/control-limit key in the documented schema. No slot column; only the `wafer_id` string — `PKL:207`.
- "CD spec window and BSM pass band" are stated as invented values; the office substitutes fleet median ±1 % — `docs/datatables/README.md:68-72`.
- The four office-gated keys (`site_layout_hash`, `recipe_revision`, `coordinate_transform_version`, `sequence_timestamp`) are omitted by the mock and derived at the office — `BE/msr_file/contracts.py:95-119`, `office_example.py:358-408`.

**Retention and availability**

- Pickles are deleted at 61 days; raw `.MSR` is not purged — `PKL:24-28`, `BE/msr_file/MIGRATION.md:227-231`.
- Search window is 60 days anchored on max(timestamp) — `BE/meas_hist/providers/mock.py:516`.
- `msr` is absent on 21,474 of 2,250,652 documents; `msr_check` is "Yes" on every document — `MH:39-44,83-98`.
- Office timestamps are offset-less KST treated as UTC — `docs/datatables/README.md:103-105`.
- Images exist only on the tool FTP, cached 72 h — `FTP:3-4`, `BE/msr_image/config.py:80-81`.

**Tool-family coverage**

- Hitachi only. `INDEX` maps only `cd-sem` and `hv-sem` — `BE/ebeam/_office_meas_hist.py:74-77`; "AMAT 은 measurement 소스가 없다" — `BE/meas_hist/providers/mock.py:321-331`; image root hard-coded `/HITACHI/DEVICE/HD` — `BE/msr_image/paths.py:8`. `docs/datatables/veritysem/` and `provision/` are stubs.

**Status**

- `msr_file` is "구현완료 … 사내 데이터 검증 전" — `BE/msr_file/MIGRATION.md:5-7`.

### Inferences

- The mock FDC keys `ObjectSem` and `Vrd` (`BE/msr_file/providers/mock.py:467-468`) differ in case from the documented real keys `ObjectSEM` and `VRD` (`PKL:310,314`). If the office adapter matches catalogue names exactly, those two channels would get no summary at the office. I confirmed the spellings; the consequence is inferred.
- At the office, FDC `drift_sigma` / `status` / derived `health` are judged against mock-invented nominals and sigmas until an office baseline is agreed (`PKL:445-448`), so those fields are not trustworthy evidence yet.
- Multi-wafer lots probably appear as several MSRs sharing `lot_id`; no doc confirms it.
- An expired pickle on `GET /api/msr-file` may surface as a 500, since only the download path has gone-handling.

### Gaps

- Real units, nominals and meanings of the 29 + 39 FDC keys, the vendor score scale, `dnum_group` meaning, `wafer_id` format, and alignment offset units are undocumented in the repo.
- Whether same recipe ⇒ same wafer map and same parameter set is OFFICE-VERIFY (`PKL:67-73,222-224`).
- `docs/api-contracts/msr-file.yaml` is stale against the code (units of `wafer_size` / `map_origin`, image endpoint params), so it should not be used as a source.

## 3. What analyses and visualisations exist today?

### Takeaway

Single-MSR analysis is rich (verdict sentence, wafer map, radial polynomial fit with bands, spatial layers, sector/radial profiles, FDC-per-sequence matrix, pairwise correlation, image review queue). Set-scope analysis is uneven: Time-Series and Across-MSR correlation and the FDC status matrix are built, while set-scope Position has two maps and set-scope Gallery is a placeholder. All statistics are computed in the browser except the per-parameter and FDC summaries.

### Cited Findings

**측정 개요 / Dashboard (single focus) (a)**

- Verdict block: `확인 필요` / `정상` badge and a one-sentence verdict; columns 커버리지, 산포 (3σ, σ → σ(MAD)), 이상 site (count, 군집/분산, per-sector) with "웨이퍼에서 보기" — `SK/overview/VerdictBlock.vue:5-215`.
- Verdict rule: `attention = failedCauses > 0 || outlierCount > 0`, two tiers only — `UA/verdict.ts:75`. The block states "넓다/좁다는 기준선이 없어 판정하지 않습니다" — `VerdictBlock.vue:118-151`.
- Four failure causes: `msr_check`, `align_fail` (NA = unknown), image fail, CD missing — `UA/cdu.ts:122-191`.
- Cluster rule: ≥ 3 placed sites and top sector share ≥ 0.6 — `UA/cdu.ts:231-237,296-303`.
- Acquisition strip (Wafer, Process, Mag, Vacc, Pixel) and Align-image modal with score — `SK/dashboard/Conditions.vue:36-42`, `SK/dashboard/AlignImages.vue:71-118`.
- Parameter navigator with multi-select and a flagged-parameter shortcut — `SK/dashboard/ParamNav.vue:19-108`.
- Wafer map: ECharts `scatter` (Field) or `custom` rects (Die, die mean), outlier rings, failure ✕, notch, options for grid / die border / MP labels / manual colour range, maximise modal — `SK/WaferMap.vue:145-313`, `SK/WaferMapOptions.vue:16-80`.
- Radius plot: value vs radius with 1°/2°/3° polynomial fit; full-screen dialog adds IQR / 95 % confidence / 95 % prediction bands, sector colouring, adjusted R², RMSE, CV RMSE (PRESS), residual σ and MAD, Δ trend, largest residual — `SK/dashboard/RadiusAnalysisDialog.vue:198-275`, `FE/utils/radialAnalysis.ts:167-369`.
- Parameter summary table (backend numbers) and Measurement Points table (sortable, multi-select, 전체 / 이상·실패 filter, status badges) — `SK/dashboard/ParamSummary.vue:64-81`, `SK/dashboard/MeasurementPoints.vue:193-290`.
- Distribution: Hist (12 bins) / Box / Violin — `SK/dashboard/Distribution.vue:6`, `SK/DistributionChart.vue:69`.
- SEM image panel with zoom (1–6×), HV-SEM variant chips, single/all mode, full-screen viewer — `SK/dashboard/SemImage.vue:18-218`, `SK/ZoomableImage.vue:105-107`.
- Linked selection: `focusedSequence` is shared by wafer map, radius chart, points table, SEM image and FDC cursor; `selectedSites` (set only by the points table) drives halos on map, radius and distribution — `FE/composables/useSkewvoirAnalysis.ts:313-340,372-379`.

**위치 비교 / Position (a)**

- Single: four evidence chips (centre–edge delta, direction contrast, largest local residual, coverage); layer map Raw / Centered / Residual / Failure with optional scan path; radial profile (median + IQR band); sector profile table; site detail table; site evidence drawer with SEM preview and raw cond text — `SK/position/SpatialWorkbench.vue:34-175`, `SK/position/SpatialLayerMap.vue:26-156`, `SK/position/SiteEvidenceDrawer.vue:14-131`.
- Formulas: centered = raw − wafer median; residual = raw − linear radial fit; sectors are four 90° wedges; notch defaults to `'bottom'` with `notchValidated: false` — `UA/spatial.ts:161-174,214-215,274-275,373`.
- Set: Composite Mean map, Site Variability (σ) map, and a Wafer Stack list only — `SK/views/PositionStack.vue:25-78,107-128`.

**FDC 분석 (a)**

- Single: parameter matrix (ECharts 6 `matrix`, one sparkline per channel with nominal line and Pearson r vs CD) or individual panes; sequence event lane (fail / image / alignment dots); axis mode parameter-scoped or whole-MSR; data-mismatch badge — `SK/fdc/SequenceWorkbench.vue:62-299`, `SK/fdc/ParamMatrix.vue:96-242`, `UA/paramMatrix.ts:17-21,149-196`.
- Set: run × channel status matrix (DOM table): raw mean and ±σ vs the other runs; needs ≥ 5 runs; watch 2σ, abnormal 3σ — `SK/views/Fdc.vue:28-66`, `UA/fdcSet.ts:114-127,181-190`. The view states it is "탐색 비교이며 고정 장비 관리 한계가 아닙니다" — `SK/views/Fdc.vue:46-51`.

**Time-Series (set only) (a)**

- `scope=single` shows only a placeholder card — `SK/views/TimeSeries.vue:377-387`.
- Lenses 추이 / 분포 / 장비 skew; x-axis time / order / eqp; baseline raw or residual vs per-recipe median — `SK/views/TimeSeries.vue:416-454`, `UA/timeSeries.ts:70-95,142-150`.
- Trend chart: one line per tool, min/max band, verdict-coloured dots, click sets focus — `SK/TimeSeriesChart.vue:137-367`.
- Anomaly detection with editable thresholds: leave-one-out `range` (10 % watch / 20 % abnormal, min n 3) or `stddev` (2σ / 3σ, min n 5), on both mean and std — `FE/utils/anomaly/types.ts:41-50`, `FE/utils/anomaly/score.ts:20-66`.
- Tool skew table: per-tool offset vs per-recipe median over recipes run by ≥ 2 tools, with σ; no test or CI — `UA/timeSeries.ts:297-374`, `SK/timeseries/ToolSkewPanel.vue:39-198`.
- Sequence Trend below: one line per measurement, coloured by tool — `UA/timeSeries.ts:503-559`.

**상관 / 분포 (a)**

- Single: X = CD parameter; Y = another CD parameter (joined by chip) or a dynamic FDC channel (joined by sequence); grouping none / radius thirds / sector. Shows Pearson r, Spearman ρ, pair N, missing N, OLS line, marginal Hist / ECDF / Box / Violin, group boxes, paired-evidence table — `SK/views/Correlation.vue:18-98,290-336`, `UA/relationships.ts:76-250`, `SK/factor/RelationshipSummary.vue:33-69`.
- Set: one MSR = one point; axes from a feature registry (`level`, `spread`, `coverage`, `failure`, `spatial`, `fixed_fdc.*`, `dynamic_fdc.*#mean|std|range`); pooled and per-tool r / ρ with suppression below n = 3 — `UA/acrossMsr.ts:45-62,113,160-245`, `UA/features.ts:153-301`, `SK/factor/AcrossMsrSummary.vue`.
- Fixed chips "연관이며 원인 증명이 아님"; a demo-data note appears when Y is FDC and data is mock — `SK/DemoDataNote.vue:29`.

**이미지 갤러리 (a)**

- Single: review queue of the active parameter's rows. Reasons: `failure`, `residual` (|radial residual| above the Tukey upper fence). Vendor-score badge below the Tukey lower fence. Fixed sort order; filters 이상·실패 우선 / 이미지 없음 제외 / text; die-lattice or list layout; thumbnail 72–240 px — `UA/gallery.ts:198-351`, `SK/gallery/ReviewFilters.vue`, `SK/gallery/ImageGrid.vue`.
- Viewer: prev/next and arrow keys, zoom/pan, raw cond.txt text, variant chips, metadata rail, "wafer 위치 이동" — `SK/gallery/ImageViewer.vue:128-374`.
- Set: only the focus MSR's images as a filename grid, marked "Task 12 replaces" — `SK/views/Gallery.vue:91-134`.

**Compatibility gate (a)**

- A set member is excluded on recipe / unit / method / layout mismatch or missing metadata; three capabilities share one readiness value — `UA/compatibility.ts:158-183,251-282,336-340`.

**Where statistics are computed**

- Frontend primitives: mean, sample std, R-7 quantiles, MAD × 1.4826, Tukey fences, Pearson, Spearman, OLS — `FE/utils/stats.ts:6-158`.
- Backend: only the per-parameter and FDC summaries (section 2).

**Things that do not exist (a, negative findings)**

- No p-values, confidence intervals on correlations or offsets, significance tests, robust regression, or control-chart rules (I-MR, EWMA, CUSUM) in any skewvoir file.
- No cond.txt crosshair overlay and no `?clean=1` in skewvoir; they exist only in recipe-open and live-alarm (`FE/composables/useCondCrosshair.ts`, `FE/components/ebeam/recipeOpen/AlignPopup.vue`, `FE/components/live-alarm/AlignImagesModal.vue`). Removed from skewvoir by commit `0bbd102e` (2026-09-03).
- No image compare / side-by-side, no annotation, no measurement overlay or line profile.

### Inferences

- (c) The single definition of an outlier (leave-one-out ±10 % / ±20 % of the mean) is coarse for CD work: a 20 % deviation on a 30 nm CD is 6 nm. The thresholds are editable only on the Time-Series view, yet the same `anomalyCfg` object feeds the Dashboard's site verdicts and the feature rows (`FE/composables/useSkewvoirAnalysis.ts:418,421,750`), so an edit there likely changes other views without any visible control on them.
- (c) In a mixed-recipe set, anomaly peers are the whole set regardless of recipe or tool, so recipe-level differences can be flagged as anomalies; only the baseline is per-recipe.
- (c) The Position residual layer and the verdict's spatial pass always use a linear fit, independent of the Dashboard 1°/2°/3° toggle (`UA/spatial.ts:215`), so the two screens can disagree about the same wafer.
- (c) σ shown in the Distribution panel and parameter table is the backend `std`, while the verdict uses a client-side `sampleStd`; they can differ if populations differ.
- (c) The Time-Series y-axis label is hard-coded "Δ vs 세트 기준" even when the baseline is per-recipe (`SK/TimeSeriesChart.vue:198-203`).

### Gaps

- Whether the radial/sector approach matches what engineers actually look for (e.g. field-level or slit signatures) cannot be judged from code.
- `DistributionChart.vue` and `SequenceTrend.vue` were grepped, not read in full.

## 4. What data is fetched but never displayed or analysed, and which obvious analytic operations are absent?

### Takeaway

A meaningful amount of already-delivered data is dropped on the floor (timing fields, FDC drift summaries, alignment offsets, per-point acquisition metadata, a fully computed provenance layer), and the absent operations cluster around three things: comparison against a fixed reference, anything time-of-day or event based, and getting results out of the page.

### Cited Findings

**(b) Fetched or available but unused**

| Data | Where it arrives | Status |
| --- | --- | --- |
| `meastime`, `start_time`, `end_time` | `MeasHistRow` | Not read by any skewvoir file; used only in `RecipeMeasHistView.vue:133` and `hardware/RecipeWindowSlideover.vue` |
| `lot_cd`, `eqp_model_cd`, `fac_id`, `vendor_nm`, `tool_type`, `idp_name`, `idw_name` | `MeasHistRow` | Never read off a meas_hist row in skewvoir |
| `fdc_params[].drift_sigma`, `.status`, `.std`, `.min`, `.max` | `MsrFileResponse` | No reader; the set matrix recomputes status from `mean` (`UA/fdcSet.ts:156-171`) |
| `fixed_fdc` | `MsrFileResponse` | Used only as a set-scope correlation axis (`UA/features.ts:223,323`); not shown in the FDC view; not selectable in single scope |
| `alignment.offset` x / y | `MsrFileResponse` | Only element `[0]` (method) is read (`SK/overview/VerdictBlock.vue:386`, `SK/dashboard/AlignImages.vue:116`) |
| `measurement_score`, `addressing1/2_score` | `MsrFileRow` | Gallery badge and a boolean dot only (`UA/gallery.ts:174-175,337-338`, `UA/sequence.ts:167`); no map, trend or table column |
| `object_type`, `meas_kind`, per-row `mag` / `vac` / `pixel` signature sets | `MsrFileRow` | Extracted into the compatibility signature but never compared or rendered (`UA/compatibility.ts:113-133`) |
| `dnum_group` | `MsrFileRow` | Unused (comment only, `UA/compatibility.ts:385-393`) |
| `sequence_count`, `health`, `spm_dict` | `MsrFileResponse` | Unused; `health` and `spm_dict` are deliberately banned (`UA/features.ts:24-28`) |
| `exe_detail_info.idp_name`, `.idw_name`, `.lot_id` | `MsrFileResponse` | Extracted or ignored; never shown |
| `sequence_timestamp`, `coordinate_transform_version` | office-only keys | No occurrence in `FE/` |
| Provenance (`DerivedValue`: n, missing, transform, reference, version) | computed in `UA/features.ts` | `SK/ProvenanceDrawer.vue` is never mounted and `useProvenance().open` has no caller (grep confirmed) |
| `dynamic_fdc` slope per MSR | computed in `UA/features.ts` | Deliberately not offered as an axis (`UA/acrossMsr.ts:30-40`) |
| `ECDF` mode | `SK/DistributionChart.vue:177-206` | Not offered on the Dashboard toggle (`SK/dashboard/Distribution.vue:6`) |
| cond.txt contents | `X-Msr-Cond` header | Shown as raw `<pre>` text only; not parsed |
| `POST /api/msr-files/download`, `GET /api/msr-images`, `GET /api/meas-hist/window` | backend | No skewvoir caller (section 2) |
| URL params `ref`, `metric`, `grain` | `FE/composables/useSkewvoirRoute.ts:61-67` | Parsed and preserved, no consumer |

**(b) Data in other backend features that shares a join key** (not joined today)

- `hardware/bm_pm`: `eqp_id` + `down_dt`..`equp_dt` — `docs/datatables/hitachi/hardware_bm_pm.txt:34-48`.
- `live_alarm`: `eqp_id` + `occurred_at`, plus `lot_id`, `recipe_id` — `BE/ebeam/live_alarm/contracts.py:82-120`.
- `hardware/fdc` fleet: `eqp_id` + `timestamp`, CD-SEM only — `docs/datatables/hitachi/hardware_network_fdc_cdsem.txt:4-19`.
- `recipe_search`: `recipe_name` + `fab_name` → IDP/AMP including `Design_Value` and `Target` — `docs/datatables/hitachi/recipe_idp.txt:805-825`, `BE/ebeam/recipe_search/contracts.py:187-191`.
- `tttm`: `EpochMarker{eqp_id, date, kind}` for MDC / BM / PM epochs — `BE/ebeam/tttm/contracts.py:133-147`.

**(a) Export and sharing that exists**

- Excel and clipboard for the Measurement Points table only — `SK/dashboard/MeasurementPoints.vue:384-416`.
- PNG download on every ECharts chart — `FE/composables/useEchart.ts:270-300`.
- TIFF original download; raw `.MSR` / pickle for the focus; short-link share; 요약 복사 (describes the focus MSR only) — `SK/workspace/LeftRail.vue:444-524`.

**Absent operations, already named in project docs**

- Fixed baseline vs target comparison (S7), accepted but not built — `docs/research/2026-10-06-page-value-plans.md:352-404`.
- Review receipt xlsx (S8), accepted, after S7, not built — same file `:458-503`.
- Set-scope reference median / signed delta / coverage maps — `docs/issues/skewvoir/analysis-coverage-gap-analysis.md` §3.2, §7.1; still absent (`SK/views/PositionStack.vue:4` "kept until Task 6").
- Same-site-over-time image strip — same doc §3.6, §7.3; still absent (`SK/views/Gallery.vue:91`).
- BM/PM event band and multi-lane Time-Series — same doc §3.4 (needs a backend event contract).
- Per-MSR annotation — `.scratch/skewvoir-annotation/issues/01-per-msr-annotation.md` (`needs-triage`, deferred).

### Inferences

All items below are inference (c): operations the existing data could support, with the constraint that applies.

- **Run-time and throughput reading.** `start_time`, `end_time`, `meastime` are already on every set member; a per-run duration or per-point time column in Time-Series needs no backend change.
- **Tool-recorded FDC drift.** `drift_sigma` / `status` arrive with every file; showing them would be trivial, but they rest on mock-invented nominals (section 2), so they would need an explicit "not an office baseline" label or should stay hidden until one exists.
- **Alignment offset trend.** `alignment.offset` x/y and `score` per MSR could become set-scope features alongside `fixed_fdc`; units are undocumented.
- **Vendor score as a spatial layer.** `measurement_score` could be a fifth layer on the Position map. The method research excludes vendor scores from the judgement path, so it would have to be display-only.
- **Fixed FDC in the single-MSR FDC view.** It is one scalar per MSR, so a small "pre-measurement condition" table is the natural form.
- **Result export beyond one table.** Tool-skew table, across-MSR points, paired evidence, spatial site table, FDC status matrix and radial fit metrics have no data export; the existing `useTableDownload` path already handles xlsx.
- **Bulk original download for a set.** The endpoint exists and has no caller.
- **Provenance drawer.** The data layer is complete and the component exists; it is only unmounted. Note commit `358f3fe8` removed it deliberately, so re-mounting needs the owner's reason first.
- **Design value as a reference line.** `Design_Value` per (recipe, parameter) is the only candidate target in the repo, but docs conflict on whether the parser returns it (`docs/datatables/README.md:80-82` vs `recipe_idp.txt:799-803`); treat as unverified. Using it means a cross-feature call, which falls under the cross-page-link maintainability rule in spirit.
- **Event overlay.** BM/PM, alarms and MDC epochs share `eqp_id` + time with every set member. This needs backend work in skewvoir's feed or a client-side second fetch; the KST-as-UTC timestamp convention (and `live_alarm`'s explicit `+09:00`) makes the join error-prone.
- **Wafer-map spatial signatures beyond radial + four sectors**, cross-recipe or cross-fab comparison, and image quality metrics are not supported by any current derivation; image metrics would need image bytes processed somewhere, which no current code does.
- **Not supportable now:** Cp/Cpk and pass/fail (no spec or target contract — `docs/research/2026-10-05-page-value-brainstorm.md:451`), SPC limits from a user-selected set (explicitly forbidden — `docs/issues/skewvoir/wafer-analysis-method-research.md:25-26`), FDC↔CD causal claims at home (fabricated), AMAT families (no measurement source), per-second FDC rates (no per-sequence timestamp).

### Gaps

- Whether engineers want any of these is unknown; there is no usage or interview evidence in the repo.
- The real cond.txt key set for measurement images is OFFICE-VERIFY (`FTP:120-121`), so what parsing it would yield is unknown.

## 5. What UI/UX friction is visible in the code?

### Takeaway

Friction is concentrated in four places: user choices that are not shareable or do not survive a view switch, uneven loading/error handling across panels, set-scope views that are thinner than their single-scope twins, and silent limits.

### Cited Findings

**State that is lost**

- Views are swapped by `v-if` (`SK/Workspace.vue:43-70`), so component-local refs reset on every view switch. Affected choices include: wafer map Field/Die and manual colour range (`SK/dashboard/WaferMap.vue:95-97`), radius degree (`SK/dashboard/RadiusPlot.vue:70`), radius dialog model / band (`RadiusAnalysisDialog.vue:198-200`), points table filter and sort (`MeasurementPoints.vue:185,204-205`), distribution mode (`Distribution.vue:41`), spatial layer and scan path (`SpatialLayerMap.vue:99-100`), FDC matrix vs individual mode and selected graphs (`SequenceWorkbench.vue:326-327`), correlation set-scope X/Y axes (`SK/views/Correlation.vue:182-183`), correlation Y kind / FDC channel / grouping (`:225-231`), gallery text filter (`SK/views/Gallery.vue:229-230`).
- Not in the URL, so not in a shared link: all of the above, plus the anomaly method and thresholds (`useState('skewvoir-anomaly-cfg')`, `FE/composables/useSkewvoirAnalysis.ts:49-53`), selected sites, and extra parameters.
- Search state (query text, results, sort, date range) is `useState`, lost on reload — `FE/composables/useMeasHistSearch.ts:93-94,162-172`. Only dropdown picks and the selection persist in localStorage.

**Loading and error handling**

- `focusError` with a retry button is read only by `SK/position/SpatialWorkbench.vue` and `SK/fdc/SequenceWorkbench.vue` (grep confirmed). Dashboard, Correlation and Gallery fall to empty text on a failed focus fetch.
- A failed set batch is swallowed silently — `FE/composables/useSkewvoirAnalysis.ts:529-531`; only Time-Series shows "N개 측정의 파일을 불러오지 못했습니다" (`SK/views/TimeSeries.vue:42-49`).
- VerdictBlock, Conditions, AlignImages, ParamNav and ParamSummary have no loading state.
- Set-scope Correlation keys only on `focusPending`, not on set loading.

**Thin or uneven set scope**

- Time-Series is empty in single scope; Gallery and Position are thin in set scope (section 3). The left rail's member list is clickable on some views and inert on others by design (`SK/workspace/LeftRail.vue:262-270`).
- The set editor's candidate pool requires `msr_check === 'Yes'` (`FE/composables/useSkewvoirAnalysis.ts:454-456`) while search does not gate on it.
- Set-scope gallery tiles are not clickable unless TIFF — `SK/views/Gallery.vue:100-134`.

**Silent limits**

- 30-member cap applied after navigation (`UA/curatedSet.ts:17`).
- Client-side sort over loaded rows only.
- 60-day search window and 61-day pickle retention; recents use their own hard-coded 60 (`FE/composables/useSkewvoirRecentlyViewed.ts:21`).
- Gallery card shows only the first HV-SEM variant (`UA/gallery.ts:66-67`).
- Gallery does not warm the image cache; only the Dashboard does (`SK/views/Dashboard.vue:104`).

**Labels and discoverability**

- Acquisition strip values carry the field name only in a `title` attribute — `SK/dashboard/Conditions.vue:36-42`.
- Multi-select of parameters is by ⌘/Ctrl/⇧+click — `SK/dashboard/ParamNav.vue:99-101`.
- `q:` prefix is undocumented in the help popover.
- Notch orientation is an unvalidated default, shown as "Phase-1 검증 기본값" — `SK/position/SectorProfile.vue:17`.

**Flags and leftovers**

- No feature flag gates any skewvoir view. The only data-mode gate is the demo note.
- Stale markers: "Task 6", "Task 12", "Task 4/8/10", "Task 3" comments point to a plan no current doc carries; `FE/utils/features.ts:34` still calls skewvoir "a placeholder".
- Dead code: `SK/ProvenanceDrawer.vue` + `FE/composables/useProvenance.ts`; `clearSelectedSites` has no consumer.
- The user-facing changelog has one skewvoir entry (v3.0, 2026.07) and nothing since — `FE/data/skewnonoHistory.ts:56-60`.

**Design constraints that apply**

- FHD 1920×1080 is the target; sub-`lg` is not — `DESIGN.md:440,633,636`.
- Rail rule: controls that change what is analysed live in the rail — `DESIGN.md:442`.
- Data values never below 12px — `DESIGN.md:385,595`. Status colours only from `--sk-ok/warn/bad` — `DESIGN.md:656`.

### Inferences

- (c) The anomaly-threshold editor violates the spirit of the rail rule: it changes what every view judges, but lives inside one lens of one view and is neither persisted nor shareable. Two engineers opening the same link can see different verdicts.
- (c) A shared Correlation link in set scope reopens on default axes, so the link does not reproduce the screen the sender saw — contrary to the stated URL principle (`UA/routeQuery.ts:3-6`).
- (c) Components without a loading state probably keep showing the previous MSR's numbers while the next loads, since `loadFocus` does not clear `focusFile` first.
- (c) Dashboard min-height is 49rem per column plus verdict block and navigator, which likely needs scrolling inside the workspace at 1080px height; not measured.

### Gaps

- No browser run: real load times, FTP image latency at the office, and layout overflow at 1920×1080 are unverified.
- No user feedback on any of this exists in the repo.

## 6. What do design and planning docs say was intended or deferred?

### Takeaway

The intended end state is a workspace that finds spatial evidence in one measurement, confirms change across compatible history, and narrows causes with tool evidence. The owner has accepted two next steps (S7 fixed baseline comparison, S8 review receipt) and explicitly gated or rejected SPC limits, Cp/Cpk, tool-matching verdicts and anything needing a new index.

### Cited Findings

**Decisions any proposal must respect**

- Cross-page links need three conditions (target owns a URL contract; source has the identifier without guessing; link is a pure function owned by the target) — `docs/research/2026-10-05-page-value-brainstorm.md:134-163`.
- No new OpenSearch index or mapping for non-core features — same doc `:517`.
- The nine page-value items must need no backend change: "백엔드를 고치고 싶어지면 그 항목의 범위가 틀린 것입니다" — `docs/research/2026-10-06-page-value-plans.md:64-66`.
- Pure functions with `.test.ts` first; components only draw — same doc `:67-69`.
- No control limits from a user-selected set — `docs/issues/skewvoir/wafer-analysis-method-research.md:25-26,293`.
- Cp/Cpk gated on registered USL/LSL and a stable regime — `docs/issues/skewvoir/analysis-drilldown-benchmark-research.md:305-318`; rejected for now — brainstorm `:451,514`.
- Tool matching gated on a reference artifact; otherwise "tool 차이 후보만 표시" — benchmark `:248-253,448`. Sets under 50 samples rejected for TTTM-style claims — `docs/research/2026-08-16-skew-tttm-feasibility.md` §7.6–7.7.
- `health`, placeholder `spm_dict` and vendor scores are excluded from the judgement path — method research `:74-81,521`.
- Unknown-safe rule: "평가할 수 없으면 정상으로 바꾸지 않고 `평가 불가`와 이유를 표시" — method research `:561`; encoded in `UA/types.ts:4-10`.
- Banned wording: "악화", "원인", "추천", "공식 기준", "안전" — plans `:74-76`.
- Tool family is a `providers/` axis, not a path — `docs/adr/0006-page-grouping-by-domain-and-object.md:102,161`.
- ADR 0006 makes 스큐보아 an independent domain with its own shell; execution is deferred until after VeritySEM / Provision onboarding — same ADR `:143,153,191-196`.

**Status of planned ideas** (status as written in the doc; "now" from code)

| Idea | Source | Doc status | Now |
| --- | --- | --- | --- |
| S2 측정 이력 → 스큐보아 분석 | plans `:86-135` | 채택 | Shipped 2026-10-06 (`edb5c692`) |
| S7 기준·대상 고정 비교 (`base=` key) | plans `:352-404` | 채택 (조건부) | Not built |
| S8 검토 영수증 (xlsx, no images) | plans `:458-503` | 채택, after S7 | Not built |
| S15 포인트 축소 민감도 | brainstorm `:446,515` | 제외 (2026-10-06) | — |
| S17 알람 → 스큐보아 검색 | plans `:333-350` | 채택 (link) | Not wired |
| 검색 결과 실패 우선 정렬 | brainstorm `:447` | 후보 | — |
| 검토 결과 공유 저장 | brainstorm `:450` | 제외 (지금) | — |
| Set reference median / signed delta / coverage map | gap analysis §5 #4 | 보류 | Not built |
| Evidence pack | gap analysis §5 #5 | 보류 | Superseded by S8 in scope (inference) |
| Same-site image strip | gap analysis §5 #6 | 보류 | Not built |
| BM/PM band, 4-lane Time-Series | gap analysis §5 #7 | 계약 대기 | Not built |
| I-MR / EWMA / Cp/Cpk / tool matching | gap analysis §5 #8 | 계약 대기 | Not built |
| TTTM lens in skewvoir (pairwise, order balance) | TTTM feasibility §7.4, §7.7 | planned | Not built |
| Per-view usage beacon | view-usage spec | 승인된 설계 | Not built |
| Official MSR review assessment | `.scratch/skewvoir-msr-review/spec.md` | `ready-for-agent`, 8 of 9 map issues open | Not built |
| Per-MSR annotation | `.scratch/skewvoir-annotation/issues/01` | `needs-triage`, deferred | No UI (`SK/workspace/LeftRail.vue:501-502`) |

**What the 2026-08-16 gap analysis got superseded on**

- Its #1–#3 shipped the same day (commits `633e6dcd`, `40646a26`, `641c02cf`); #3 (CDU card + failure cards) was replaced on 2026-08-22 by the single verdict block (`38132322`).
- Its "set 범위는 안내 카드만" (FDC) and "`Task 10 replaces later`" (Correlation) rows are stale.
- Its open policy question (is the focus included in the reference?) is answered elsewhere: "focus MSR은 자신의 reference 계산에서 제외합니다" — benchmark `:137`.

**Open issues**

- `.scratch/skewvoir-msr-review/`: issue 01 resolved (quality gates, then leave-candidate-out median/MAD, plus frozen EWMA); 02 (office inventory) and 08 (human review outcomes) are unblocked and open; 03–07 and 09 are blocked.
- `.scratch/skewvoir-annotation/issues/01`: needs an office write path; "Do not start while Phase 2 office wiring of the 16 read-only features is still pending."

**Contradictions in the docs**

- The October plan says a per-view beacon "인덱스 변경이 필요하므로 만들지 않습니다" (plans `:53-54`), while the August view-usage spec was designed to need none (`docs/superpowers/specs/2026-08-04-skewvoir-view-usage-design.md:228-233`).
- The msr-review research retires fixed leave-one-out mean/σ for official use, yet that is the only detector in code (`FE/utils/anomaly/types.ts:41-50`).
- Vocabulary differs: `CONTEXT.md` prescribes 검토 표시 없음 / 주의 / 검토 필요 / 미평가; code uses 정상 / 주의 / 이상 / 판정 불가.
- `CONTEXT.md` has no entries for MSR, MP, sequence, focus, set scope or verdict.
- Rate limit is quoted as 50 / 5 s in one doc and 20 / 5 s in another; code says 50 (`BE/__init__.py:101`).

### Inferences

- The owner's direction of travel is clear from what was accepted vs rejected: comparisons the user defines by hand and labels as exploratory are in; anything that reads as an official verdict, a spec judgement or automatic cohort selection is out until an office contract exists.
- S7 + S8 together address two of the three "빠진 것" the owner listed (fixed reference, recording a conclusion); the third (point reduction) was excluded on 2026-10-06.
- The msr-review spec being `ready-for-agent` while its own map lists eight open decisions suggests it is not actually ready; treat it as a design direction, not a backlog item.

### Gaps

- `DESIGN.md` was read in sections, not in full; the 701-line file may hold further constraints relevant to a dense analysis workspace.
- No doc records whether the batch-1 confirmation plan (compare `/activity` counts before and after, plus three direct questions — plans `:49-58`) was ever run.
- Whether the owner still intends S7 → S8 in that order as of 2026-10-09 is not recorded anywhere after 2026-10-06.
