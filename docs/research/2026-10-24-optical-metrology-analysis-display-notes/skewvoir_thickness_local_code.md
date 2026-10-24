# Code Context — skewvoir data path vs. optical metrology (thickness / SE)

RESEARCH ONLY. No repo files were edited. Everything below is read from the working tree at
`/Users/daeyoung/Codes/skewnono_v3_nuxt`.

## Files Retrieved

1. `frontend/app/pages/ebeam/cd-sem/skewvoir/index.vue` (1-17) — the skewvoir **search landing** page; a 3-line
   wrapper around `EbeamSkewvoirSearchLanding` with `tool-type="cd-sem"`.
2. `frontend/app/pages/ebeam/cd-sem/skewvoir/analysis.vue` (1-17) — the skewvoir **workspace** page; wrapper around
   `EbeamSkewvoirWorkspace`. HV-SEM mirrors both at `frontend/app/pages/ebeam/hv-sem/skewvoir/{index,analysis}.vue`.
3. `frontend/app/pages/thickness/index.vue` (1-27) — **stub only**. "Thickness Metrology … coming soon", hidden from
   nav as of the AFM swap (2026-05). No data path exists.
4. `frontend/app/components/ebeam/skewvoir/SearchLanding.vue` (1-80) — search page layout.
5. `frontend/app/components/ebeam/skewvoir/Workspace.vue` (1-121) — analysis layout + the 6-view switch.
6. `frontend/app/composables/useSkewvoirWorkspace.ts` (1-121) — view modes + `SkewvoirSelection`.
7. `frontend/app/composables/useSkewvoirRoute.ts` (49-131) — every URL query key the workspace owns.
8. `frontend/app/composables/useSkewvoirAnalysis.ts` (37-250) — data layer: focusFile / setFiles / trendPoints.
9. `frontend/app/composables/useMsrFileApi.ts` (20-244) — **the measurement-record contract** as the frontend sees it.
10. `frontend/app/composables/useMeasHistApi.ts` (8-170) — **the measurement-history row contract** (the list/search axis).
11. `frontend/app/utils/skewvoirAnalysis/types.ts` (1-191) — unknown-safe compatibility/readiness types.
12. `frontend/app/utils/skewvoirAnalysis/timeSeries.ts` (1-60) — the set-trend record shape.
13. `frontend/app/utils/skewvoirAnalysis/features.ts` (1-80) — per-MSR feature registry + provenance.
14. `frontend/app/utils/skewvoirAnalysis/routeQuery.ts` (1-70) — URL⇄state translation, `(unnamed)` sentinel.
15. `frontend/app/utils/skewvoirLinks.ts` (1-40) — `hasSkewvoir()` is limited to `cd-sem`/`hv-sem`.
16. `frontend/app/utils/waferMapOptions.ts` (1-49) — wafer-map display options contract.
17. `frontend/app/composables/useEchart.ts` (1-80) — the single ECharts wrapper (44 consumers).
18. `backend/msr_file/routes.py` (1-197), `backend/msr_file/data.py` (1-65), `backend/msr_file/contracts.py` (1-120),
    `backend/msr_file/providers/mock.py` (1-60, 258-292, 400-437, 745-760, 1130-1192) — the SEM detail payload.
19. `backend/msr_file/MIGRATION.md` (1-50) — office adapter rules + response contract.
20. `backend/meas_hist/contracts.py` (1-60), `backend/meas_hist/routes.py` (18-105),
    `backend/meas_hist/providers/mock.py` (symbol map) — the history index.
21. `backend/afm/contracts.py` (1-120), `backend/afm/data.py` (1-99), `backend/afm/routes.py` (route map),
    `backend/afm/MIGRATION.md` (1-60) — **the precedent for a non-SEM modality**.
22. `backend/_runtime/office_registry.py` (1-60), `backend/_runtime/data_provider.py` (1-50) — provider swap mechanics.
23. `backend/_logging/feature_map.py` (1-60) — feature slug + family vocabulary (`AFM_FAMILY = "afm"`).
24. `docs/datatables/README.md` (whole) — the file→source→feature table, naming + provenance conventions.
25. `docs/datatables/hitachi/msr_file_pickle.txt` (1-60), `docs/datatables/hitachi/meas_hist.txt` (1-50) — real field names.
26. `docs/datatables/afm/afm_redis.txt` (1-40) — the AFM source doc, incl. serialization/retention rules.
27. `docs/afm-migration-plan.md` (1-140), `docs/afm/feature-summary.md` (1-90) — modality onboarding precedent.
28. `docs/research/2026-10-09-analysis-service-directions.md` (whole) — current analysis roadmap.
29. `docs/adr/0006-page-grouping-by-domain-and-object.md` (40-70) — Thickness is ruled an **independent domain**.
30. `CLAUDE.md` (27-160), `.github/workflows/ci.yml` (whole) — constraints and gates.

## Key Code

### 1. Where skewvoir lives and what the pages are

Routes (all four are ≤17-line wrappers; all logic is in `components/ebeam/skewvoir/`):

- `/ebeam/cd-sem/skewvoir` → `EbeamSkewvoirSearchLanding` (`index.vue:1-6`)
- `/ebeam/cd-sem/skewvoir/analysis` → `EbeamSkewvoirWorkspace` (`analysis.vue:1-6`)
- `/ebeam/hv-sem/skewvoir{,/analysis}` → the same two components with `tool-type="hv-sem"`

Both pages set `definePageMeta({ hideFabSidebar: true, lockDesktopPageScroll: true })` and call
`useNavigation().setToolType(...)` — skewvoir runs its **own shell**, not the standard header+tabs page
(`docs/adr/0006:58`: "다른 상호작용 모델 … 자체 셸만").

**Search landing layout** (`SearchLanding.vue:1-80`): a 2-column grid —
left master column = `SearchBar` (free-text with `eq:`/`recipe:` tokens) + `FilterBar` (fab/model/eq/lot/date facets)
+ `SearchScopeStrip` (retention/capped notice) + `SelectionWorkbench` (the multi-select cart, "Analyze" → set route);
below it a `ResultTable` (sortable, load-more, checkbox multi-select); right rail =
`RecentMeasurementsRail`.

**Workspace layout** (`Workspace.vue:1-82`): fixed-height card, left `WorkspaceLeftRail`, right a `v-if` chain over
6 views. The 6 views (`useSkewvoirWorkspace.ts:36-43`):

| kind | label | component |
| --- | --- | --- |
| `dashboard` | 측정 개요 | `views/Dashboard.vue` (ParamNav, ParamSummary, WaferMap, SemImage, Distribution, MeasurementPoints, Conditions, VerdictBlock) |
| `position-stack` | 위치 비교 | `views/PositionStack.vue` (SpatialWorkbench, RadialProfile, SectorProfile, SiteEvidenceDrawer) |
| `fdc` | FDC 분석 | `views/Fdc.vue` (SequenceWorkbench, ParamMatrix, SetStatusMatrix) |
| `time-series` | Time-Series | `views/TimeSeries.vue` (ToolSkewPanel, BaselineBlock, ParamCoverageList) |
| `correlation` | 상관 / 분포 | `views/Correlation.vue` (AcrossMsrScatter, PairedEvidenceTable, RelationshipSummary) |
| `gallery` | 이미지 갤러리 | `views/Gallery.vue` (ImageGrid, ImageViewer, EvidenceCard, ReviewFilters) |

Plus `ReadinessModal` (compatibility manifest) and a `ProvenanceDrawer` that is deliberately disabled
(research doc: commit `358f3fe8`).

### 2. The skewvoir data contract (exact field names)

**Two API surfaces, two grains.** The list/search grain is `meas_hist`; the detail grain is `msr_file`.

**(a) `GET /api/meas-hist{,/search,/facets,/window}` → `MeasHistRow`**
(`backend/meas_hist/contracts.py:19-45`, mirrored at `frontend/app/composables/useMeasHistApi.ts:8-40`):

```text
id, fac_id, fab_name, vendor_nm ('HITACHI'|'AMAT'), eqp_id, eqp_ip, eqp_model_cd,
tool_type ('cd-sem'|'hv-sem'|'veritysem'|'provision'), lot_cd, lot_id, class_name,
recipe_name, full_name, timestamp, start_time, end_time, meastime (int seconds),
msr, msr_check ('Yes'|'No'), align_fail ('Pass'|'Fail'|'NA'), total_images,
fail_images, fail_ratio (PERCENT 0..100 — "never a fraction"), idp_name, idw_name
```

Search response envelope (`useMeasHistApi.ts:86-101`): `total, capped, recipe_names?, recipe_names_complete?,
offset, limit, range{from,to,anchor}, out_of_retention, rows[]`. Facets (`:56-70`): `anchor, retention_days,
fab[], model[], eq[]` — **no recipe facet on purpose** (comment `:64-69`).
Search params (`:72-85`) OR within a key via repeated query args: `fab, model, eq, recipe, lot, msr, q, from, to,
offset, limit`. Timestamps are **offset-less KST wall clock** (`docs/datatables/README.md` 표기 규칙).

**(b) `GET /api/msr-file?msr=&class_name=&total_images=` → `MsrFileResponse`**
(`backend/msr_file/contracts.py:32-120`, mirrored at `useMsrFileApi.ts:20-135`):

```text
msr, class_name, eqp_ip, total_images, sequence_count, health (mock-only scalar 0..1),
parameters: MsrParamSummary[], fdc_params: FdcParamSummary[],
fixed_fdc: {param: number}, dynamic_fdc: {sequence: {param: number}},
exe_detail_info: ExeDetailInfo, alignment: AlignmentInfo, spm_dict: SpmDict (PLACEHOLDER),
total, rows: MsrFileRow[]
```

`MsrFileRow` — one row = one measurement = one `sequence` (1:1, office 확인 2026-07-27,
`docs/datatables/hitachi/msr_file_pickle.txt:34-40`):

```text
msr, sequence, chip_number ("col,row"), chip_coordinate, stage_coordinate, dnum_group,
mp_number, parameter, cd_value (float|null — null exactly when mp_number < 0),
no_of_mp_image, mp_image_name_01, mp_image_names[], meas_condition_mag, meas_condition_vac,
meas_condition_pixel, addressing1_score|null, addressing2_score|null, measurement_score|null,
meas_method, object_type, meas_kind|null
```

`MsrParamSummary` (`contracts.py:66-83`): `parameter, count, mean, std, min, max, unit`.
**`unit` is DERIVED from the parameter name, not read from the data** — there is no unit column in
`df_result_data`; the unit lives on the SEM image (user-confirmed 2026-08-08). Never `""`: a blank unit is read by
the frontend as UNKNOWN and hard-excludes the MSR (`metadata-missing`) — see
`mock.py:409-430` and `utils/skewvoirAnalysis/compatibility.ts::compareToReference`.

`ExeDetailInfo` (`contracts.py:100-120`): `class_name, recipe_name, idp_name, lot_id, process, wafer_id, idw_name,
chip_array, chip_pitch, wafer_size, map_offset, map_origin` + **4 office-gated `NotRequired` keys mock must NOT
emit**: `site_layout_hash, recipe_revision, coordinate_transform_version, sequence_timestamp`.

`FdcParamSummary`: `name, category, category_label, unit, nominal, mean, std, min, max, drift_sigma,
status ('ok'|'warning'|'bad')`. `AlignmentInfo`: `image_file{}, offset{method: [method,x,y]}, score{}`.
`SpmDict`: `{vave[], Vol[], wf_len[]}` — explicitly a **seeded placeholder parabola, nothing consumes it**
(`useMsrFileApi.ts:78-88`).

Batch sibling `POST /api/msr-files` (`routes.py:37-83`) exists purely to dodge the 50-req/5s rate limit;
`MAX_BULK = 200`. Download endpoints `/msr-file/download?kind=raw|pkl` and `POST /msr-files/download` (zip, ≤100).

**(c) Frontend-side derived records.** The set/trend record is `TrendPoint`
(`utils/skewvoirAnalysis/timeSeries.ts:36-58`): `msr, label, eqpId, recipeName, ts (epoch ms|null),
mean, min, max, std, value, bandLo, bandHi, verdict?` — raw and baseline-shifted values are kept separate on
purpose. The per-MSR analysis table is `MsrFeatureRow` with `DerivedValue<T>` =
`value + unit + n + missing + transform + reference + version` (`features.ts:1-50`, `FEATURE_VERSION = 'msr-feature-v1'`),
families `level | spread | coverage | failure | spatial | fixed_fdc | dynamic_fdc | quality`. `health` and `spm_dict`
are **BANNED** from that table (`features.ts:23-27`, asserted in `features.test.ts`).

### 3. Comparison axes already supported

| axis | where it comes from | evidence |
| --- | --- | --- |
| **time** | `MeasHistRow.timestamp / start_time / end_time / meastime` | `useMeasHistApi.ts:24-27`; `TsAxisMode = 'time' | 'order' | 'eqp'` (`types.ts:184-187`) |
| **eqp / tool skew** | `MeasHistRow.eqp_id` (+ `eqp_ip` on MsrFileResponse) | `timeSeries.ts:20-30`; `toolColors.ts:1,43`; TsAxisMode `'eqp'` = one column per tool |
| **recipe** | `recipe_name` — "the grouping key for the baseline, because a measured value is a response to a CONDITION" | `timeSeries.ts:24-29`; `compatibility.ts:88` |
| **lot** | `lot_id` / `lot_cd` (search facet + receipt) | `useMeasHistApi.ts:17-18`; `receipt.ts:67,182-184` |
| **fab / model** | `fab_name`, `eqp_model_cd` facets | `useMeasHistApi.ts:56-70` |
| **wafer site (die × mp)** | `chip_number "col,row"`, `mp_number`, `chip_coordinate`, `stage_coordinate`, `dnum_group` + `chip_array`/`chip_pitch`/`wafer_size`/`map_origin` | `useMsrFileApi.ts:24-30,55-66`; `CanonicalSiteKey {die, mp}` (`types.ts:145-152`) |
| **sequence (within-MSR order)** | `MsrFileRow.sequence`, `dynamic_fdc[seq][param]` | `SequenceAxisMode = 'param' | 'all'` (`types.ts:174-181`); grain-safety rule `features.ts:14-21` |
| **parameter** | `MsrFileRow.parameter`, URL `mp` (+ `(unnamed)` sentinel for the dummy settling point) | `routeQuery.ts:46-70`; `mock.py:258-286` |
| **across-MSR arbitrary X/Y** | feature registry ids, URL `ax`/`ay` | `acrossMsr.ts:46-61,240-260` |
| **image variant** | `mp_image_names[]` suffixes `-U/-T/-M/-L` | `useSkewvoirVariantMemory.ts:1-20` |

The set scope is capped: `curatedSet.ts:17` → **30 MSRs** (picker offers 200 rows; batch limit 200).
Layout-dependent capabilities (`multiMsrDelta`, `siteVariability`, `sameSiteGallery`) are gated to `unavailable`
in mock because `site_layout_hash` is office-only (`types.ts:100-118`, `msr_file/MIGRATION.md:16-19`).

### 4. Chart inventory (all through one wrapper)

`useEchart.ts` (388 lines, 44 call sites) is the only ECharts surface: private instance, registered themes
(`utils/echartsThemes.ts`), zoom preservation (`utils/chartZoom.ts`), PNG download button, and
`onClick / onGridClick / onGridHover / onDataIndex` callbacks with `GridClickDetail`
(`x, y, gridIndex, dataPerPixelX, dataPerPixelY`) + `utils/chartNearest.ts` for pick-radius tooltips.
Colors come from `useChartPalette.ts` / `--sk-*` tokens only (`CLAUDE.md:106-108`).

Series types in use (counted over `frontend/app`): `line` 65, `scatter` 37, `bar` 16, `heatmap` 5, `boxplot` 3,
`custom` 2. Concrete reusable components:

- **Line/time series**: `ebeam/skewvoir/TimeSeriesChart.vue`, `SequenceTrend.vue`, `FdcSequenceTrend.vue`,
  `afm/trend/TrendChart.vue` (line + boxplot), `afm/trend/StabilityChart.vue`, `ebeam/hardware/BsmTrendChart.vue`.
- **1-D profile overlay — the closest existing analog to a spectrum (X/Y curves overlaid, with a leveling control)**:
  `afm/trend/ProfileOverlay.vue` (포인트 picker + 레벨링 chips, `:1-40`).
- **Scatter / paired**: `ebeam/skewvoir/CorrelationScatter.vue`, `factor/AcrossMsrScatter.vue`,
  `afm/detail/SummaryScatterChart.vue`, `afm/trend/RelationChart.vue`.
- **Distribution / box**: `ebeam/skewvoir/DistributionChart.vue` (boxplot at `:251`),
  `ebeam/hardware/MdcPanel.vue` (boxplot at `:384`), `afm/detail/HistogramChart.vue`.
- **Wafer map / spatial**: `ebeam/skewvoir/WaferMap.vue` (`type: 'custom'` at `:188`), `WaferMapOptions.vue`,
  `WaferHeatChart.vue`, `WaferDetailModal.vue`, `position/SpatialLayerMap.vue`, `dashboard/RadiusPlot.vue`
  (radial polynomial fit + CI/PI bands), `afm/detail/SiteGrid.vue` (heatmap index grid),
  `afm/detail/HeatmapChart.vue`, `afm/usage/HourHeat.vue`, `ebeam/hardware/FdcFleetView.vue`, `ebeam/tttm/FleetMap.vue`.
- **Matrix**: `ebeam/skewvoir/fdc/ParamMatrix.vue`, `SetStatusMatrix.vue`.
- `utils/waferMapOptions.ts:4-49` is the shared wafer-map option contract (`crosshair, grid, dieGrid, mpLabels,
  notch, colorMode, colorMin, colorMax`) + `resolveColorRange()`.

There is **no spectrum/dual-Y (Psi & Delta vs wavelength) chart component** in the tree; the nearest reusable
pieces are `ProfileOverlay.vue` (multi-curve 1-D overlay) and `useEchart`'s multi-grid support
(`gridIndex` in `GridClickDetail`, `useEchart.ts:12-18`).

### 5. AFM as the non-SEM modality precedent

AFM did **not** extend skewvoir or `meas_hist`. It is a fully separate vertical:

- Backend: its own feature folder `backend/afm/` with `routes.py` (12 endpoints, dual URL aliases
  `/afm/files` + `/afm-files`), `contracts.py` (6 TypedDicts), `data.py` dispatcher, `providers/{mock,office_example}.py`,
  `MIGRATION.md`, `tests/`, `__fixtures__/`. Blueprint auto-registered by the factory (`CLAUDE.md:100`).
- It is **not** an e-beam tool: no entry in `backend/ebeam/_tool_specs.py`; instead
  `_logging/feature_map.py:44-48` names it explicitly (`AFM_FAMILY = "afm"`, appended to `TOOL_FAMILIES`).
  It is exempted from the rate limit (`_EXEMPT_BLUEPRINTS`, `CLAUDE.md:150`).
- Frontend: own routes `pages/afm/index.vue` (tool picker) + `pages/afm/[tool]/{index,recipes,tips,usage,see-together}.vue`
  + `[tool]/[filename].vue`; own components tree `components/afm/**` (38 files); own composables
  `useAfmToolData / useAfmDetailApi / useAfmCart / useAfmAvailability`; own pure utils `utils/afm*.ts` (19 modules,
  each with a colocated `.test.ts`); own nav `components/nav/AfmTabs.vue`; own page identity branch
  `utils/pageIdentity.ts:119-142,215-216`.
- Shared with the rest of the app: `useEchart`, `usePersistedState`, `useTableDownload`, `--sk-*` tokens / `DESIGN.md`,
  NuxtUI, the `/s/` short links.
- Data shape is completely different from skewvoir's: `AfmMeasurementRow` (`backend/afm/contracts.py:19-72`) is a
  Redis-hash row with `unique_key, filename, date, recipe_name, lot_id, slot_number, measured_time, tool_name,
  tool_id, fab, *_dir_list[], has_* flags, point_count, tip_*`; detail is
  `AfmFileDetail {filename, tool, pickle_filename, information{}, summary[], available_points[], data[]}`
  (`:80-92`) — i.e. **an untyped per-file column dict**, because AFM columns differ per recipe (up to 51).
  Profile points are `AfmProfilePoint {x,y,z|null}` + `AfmProfileMeta {x_unit,y_unit,z_unit,data_size,surface_size}`
  (`:95-114`) — **units travel with the data and are never unified** (um/nm/pm/Pixel differ per file).
- Onboarding docs: `docs/afm-migration-plan.md` (directory mapping, URL prefix redesign, `data.py` seam, logging,
  `LASTUSER`), `docs/afm/feature-summary.md` (screen-by-screen), `docs/afm/office-data-findings.md` (841 lines of
  questionnaire answers), `docs/datatables/afm/{afm_redis,afm_raw_files}.txt`.

### 6. docs/datatables — what is documented, and nothing about thickness/SE

`docs/datatables/` is vendor-partitioned: `hitachi/` (35 docs), `afm/` (2), `provision/`, `veritysem/`, `chat/`.
`docs/datatables/README.md` carries the authoritative file→source→feature table with a `상태` column, plus rules:
docs are the truth source and the adapter follows the doc; each doc carries provenance marks
(`office 확인 YYYY-MM-DD` / `user-confirmed` / `OFFICE-VERIFY`); each `hardware_*`-style doc gets an
"어댑터 소비 규약" section; OpenSearch `text` fields need `.keyword`; timestamps are offset-less KST; use
`search_after`, not `scroll`; Redis DataFrames are parquet (`_runtime/office_redis.read_dataframe`).
New vendor folders follow `.claude/skills/add-vendor/SKILL.md`.

**There is no thickness / ellipsometry / spectrum data source documented anywhere.** A grep across `docs/**` for
`ellipsometr|spectroscop|두께|thickness|분광` returns only: external-literature snippets in
`docs/research/2026-10-09-analysis-service-directions-notes/*.md` (SE+ML as an alternative to CD-SEM overlay,
SPIE scatterometry), the "will not build" list, and ADR 0006 / migration-plan mentions of the Thickness **domain**.
`docs/research/2026-10-05-page-value-brainstorm.md:493,516` records the owner's decision:
"VeritySEM · Provision · Thickness — 측정 소스와 식별자가 확인되기 전에는 [보류]" and
**"AFM ↔ SEM ↔ Thickness 자동 연결 — 같은 웨이퍼, 같은 스텝이라는 식별자 검증이 없습니다"** (rejected).

The one thickness-adjacent thing that already exists in code: `backend/msr_file/providers/mock.py:266`
`PARAMETER_MAPPING["THICK"] = ("THICKNESS", "UNIFORMITY", "REFRACTIVE_INDEX")` with
`_PARAM_SPECS` `(("THICK",), 10.0, 100.0, "nm")` (`:406`). That is a **mock-only parameter family inside the SEM
pickle shape**, not an optical-metrology source — and note `UNIFORMITY` / `REFRACTIVE_INDEX` fall through to
`_DEFAULT_SPEC` (nm), so their units are already wrong-by-default in mock.

### 7. What adding a new modality requires (concrete paths)

Backend (per `CLAUDE.md:95-105`):
- new folder `backend/<feature>/` with `__init__.py` (re-export `bp`), `routes.py` (blueprint named `bp`, routes +
  response behaviour only), `contracts.py` (TypedDicts — the provider-independent gate), `data.py`
  (**stable dispatcher, never edited afterwards**), `providers/__init__.py`, `providers/mock.py`,
  `providers/office_example.py`, `MIGRATION.md`, `tests/`. The folder name is the global feature slug and must be
  unique or the app refuses to boot (`backend/_runtime/office_registry.py:47-56`).
- Registration is automatic: the factory rglobs `routes.py` and mounts each `bp` under `/api` — never edit
  `backend/__init__.py` (`CLAUDE.md:101`).
- Provider swap surface: `providers/office.py` (gitignored) vs `providers/mock.py`. The `cp office_example.py
  office.py` **is** the switch-on; `SKEWNONO_<FEATURE>_PROVIDER=office` with no adapter refuses to boot.
  Verify with `GET /api/health/providers`.
- Logging/identity: add the slug to `backend/_logging/feature_map.py` (never rename an existing slug; add aliases).
  Non-e-beam domains also need a family constant there (`AFM_FAMILY` precedent, `:44-48`).
- Rate limit: if the page legitimately exceeds 50 req/5s, the blueprint goes in `_EXEMPT_BLUEPRINTS`
  in `backend/__init__.py` (`CLAUDE.md:150`).
- Mock fidelity rules (`CLAUDE.md:57-90`): every new office fact lands in **both** `docs/datatables/<vendor>/<src>.txt`
  **and** `providers/mock.py` in the same change (usually the mock's docstring); copy every confirmed property
  (identifier shape, which axes vary independently, spread width, nulls) because "a mock that is tidier than the
  office is a mock that hides the office's bugs"; label guesses `OFFICE-VERIFY`.
- Docs: `docs/datatables/README.md` table row + `docs/datatables/<vendor>/<source>.txt` + `<feature>/MIGRATION.md`.
  A new vendor dir follows `.claude/skills/add-vendor/SKILL.md`.

Frontend:
- `frontend/app/pages/<domain>/…` routes; `frontend/app/components/<domain>/…`; `frontend/app/composables/use<Domain>*Api.ts`
  (`$fetch` + `joinApiPath(base, …)`, in-flight dedupe map, 429 backoff — copy `useMsrFileApi.ts:150-244`);
  pure logic in `frontend/app/utils/<domain>*.ts` with **colocated `X.test.ts`** (node:test, pure functions only —
  no Vitest/Jest/jsdom/@vue/test-utils in the tree).
- State: URL query is the source of truth for "what am I analyzing" (`useSkewvoirRoute.ts`); personal taste goes
  through `usePersistedState`. No Pinia, no TanStack Query (`CLAUDE.md:31,33`).
- If the domain is not an e-beam tool: `utils/pageIdentity.ts` branch + `utils/activity.ts` label
  (`activity.ts:140` already maps `thickness: 'Thickness Metrology'`), nav component
  (`components/nav/AfmTabs.vue` precedent), and `utils/toolType.ts` only if it is a tool family.
- ADR 0006 (`:50,58`) already rules Thickness an **independent domain**: own routes, own backend feature folder,
  own visual language, sharing only app chrome. `docs/afm-migration-plan.md:243-265` records that the Thickness
  card and the `'thickness'` branch were **removed** from the union pending reintroduction.

### 8. Constraints and CI gates

Forbidden / fixed by the repo:
- **Do not edit `data.py`** — stable dispatcher (`CLAUDE.md:43`).
- **Never edit `providers/mock.py`, `contracts.py`, `routes.py`, `office_example.py`, `tests/` when writing an
  office adapter** — only the `office.py` copy (`backend/afm/MIGRATION.md:5-11`, `backend/msr_file/MIGRATION.md:10-15`).
- No Pinia; no TanStack Query; `useAsyncData(key, fn)` with one shared cache key per resource (`CLAUDE.md:31-33`).
- No new localStorage plumbing — use `usePersistedState` (`CLAUDE.md:33`).
- Colors only from `--sk-*` tokens; `DESIGN.md` is the single visual source of truth (`CLAUDE.md:106-108`).
- No vendor/tool-family segment in backend paths; tool family is a `providers/` axis (`CLAUDE.md:99`).
- Feature directory names must be globally unique (boot failure otherwise).
- ESLint via `@nuxt/eslint`, no trailing commas, `1tbs`, 2-space indent (`AGENTS.md` Coding Style).
- Markdown: `npm run lint:md` after any doc edit; `MD060` compact tables.
- Office gate command: `SKEWNONO_<FEATURE>_PROVIDER=office .venv/bin/python -m pytest backend/<feature> -q`
  (fails with a `RuntimeError` naming the exact `cp` if the adapter is missing; never falls back to mock silently).

CI (`.github/workflows/ci.yml`): two jobs.
- `frontend` (Node 24, cwd `frontend/`): `npm ci` → `npm run typecheck` → `npm test` (`node --test` over
  `app/**/*.test.ts`). **`npm run lint` is deliberately NOT gated** (main carries pre-existing errors).
- `backend` (CPython 3.14; local/office venvs are 3.11): `pip install -r backend/requirements-dev.txt` →
  `ruff check .` **before** `python -m pytest tests backend -q`. Both roots are required — `tests/` alone silently
  skips every `backend/**/tests/` provider-contract suite. The runner has no `providers/office.py`, so an unguarded
  module-level import of it breaks collection for the whole suite; use `pytest.importorskip` /
  `pytest.skip(allow_module_level=True)`.
- No E2E, no Playwright suite, no component tests. UI changes must be verified by hand in a browser
  (`.claude/skills/browser-verify/SKILL.md`).

## Architecture

```text
Nuxt page (thin wrapper, sets tool type + page meta)
  └─ components/ebeam/skewvoir/{SearchLanding,Workspace}.vue
       ├─ useSkewvoirRoute      ← URL query is the ONLY analysis state (view, msr, msrs, mp, site, ref,
       │                           metric, grain, fdcaxis, tsview, tsx, tsb, anom, rfit, x, y, ax, ay, filter)
       ├─ useSkewvoirWorkspace  → 6 view modes + SkewvoirSelection{lot,recipe,eq,mp,msr,capturedAt}
       ├─ useSkewvoirAnalysis   → focusFile (single MsrFile) + setFiles (batch) + trendPoints
       │     ├─ useMeasHistApi  → GET /api/meas-hist{,/search,/facets,/window}   (list grain)
       │     └─ useMsrFileApi   → GET /api/msr-file, POST /api/msr-files (≤200)   (detail grain)
       └─ utils/skewvoirAnalysis/*.ts  (pure, node:test-covered: compatibility, features, timeSeries,
                                        spatial, sequence, acrossMsr, gallery, cdu, verdict, receipt, …)

Flask: routes.py → data.py (dispatcher, frozen) → providers/{mock,office}.py → contracts.py shape
       provider chosen by (mode: SKEWNONO_DATA_PROVIDER / site detection) AND (readiness: office.py exists)
```

The two grains are the structural hinge: **`meas_hist` is a one-line-per-measurement history index (the axes), and
`msr_file` is the full per-measurement payload (the values + images + FDC)**. The research doc names the absence of
such a summary layer as the shared bottleneck for both skewvoir (61-day pickle retention, 30-MSR set cap) and AFM
(20-item cart, per-item detail fetch): "측정 한 건을 한 줄로 요약한 이력 층이 없다는 것이 공통 원인"
(`docs/research/2026-10-09-analysis-service-directions.md`, §공통 벽).

## Start Here

`frontend/app/composables/useMsrFileApi.ts` — it is the single place the measurement-record contract is spelled out
for the frontend (with the nullability, optionality and office-gating rules inline), and its header comment states
that the whole cross-MSR compatibility signature is extracted **structurally** from this response. Read it next to
`backend/msr_file/contracts.py`; the pair defines exactly what a new modality would have to supply (or would fail to
supply: `site_layout_hash`, per-parameter units, a spectrum axis) to ride the same structure. Then read
`backend/afm/contracts.py` + `docs/afm-migration-plan.md` for how a modality that does **not** fit that shape was
actually integrated.

## Confidence and gaps

**Confidence: high** on items 1-4 and 6 (read the real files; contracts quoted verbatim with line refs).
**Medium** on the exhaustive chart inventory (counted by grep over `type: '…'`, so a dynamically-computed series type
could be missed) and on `useSkewvoirAnalysis.ts` internals (880 lines; I read the first ~250 and grepped the rest).

Gaps / not determined:
- I did not read `views/*.vue` bodies, so the exact panel composition inside each of the 6 views is inferred from
  the component filenames + `docs/research/2026-10-09-…md`'s description, not from the templates.
- No office source exists for thickness/ellipsometry, so **nothing in the repo tells us what a Psi/Delta spectrum or
  a film-thickness record would actually look like** — no field names, no units, no retention, no identifier that
  joins to `lot_id`/`wafer_id`. The brainstorm explicitly rejected auto-linking AFM↔SEM↔Thickness for exactly this
  reason (`docs/research/2026-10-05-page-value-brainstorm.md:516`).
- I did not verify whether `useSkewvoirAnalysis`'s cross-family resolution (`otherSemFamily`) would tolerate a
  non-SEM `tool_type`; `utils/toolType.ts:47-53` returns `null` for anything but cd-sem/hv-sem, and
  `skewvoirLinks.ts:12-16` restricts skewvoir to those two — so reusing the skewvoir workspace for a third family
  is not just unwired, it is explicitly fenced.
- Whether an ellipsometry spectrum would fit `MsrParamSummary` (scalar mean/std/min/max per parameter) at all is
  unanswered by the code: that shape has no wavelength axis. The only array-valued field in the contract is
  `spm_dict`, which is a documented placeholder nothing consumes.
- I did not run any command (no pytest, no typecheck) — research only.
