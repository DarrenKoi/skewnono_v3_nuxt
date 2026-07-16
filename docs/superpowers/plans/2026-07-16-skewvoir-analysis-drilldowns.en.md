# Skewvoir Analysis Workspace Implementation Plan (English)

> **Note:** English working copy of
> [`2026-07-16-skewvoir-analysis-drilldowns.md`](2026-07-16-skewvoir-analysis-drilldowns.md).
> The Korean file is the source of truth. Keep this file in sync when either
> changes. In-app UI strings (e.g. `측정 순서 (Sequence)`, `데모 데이터 · 방법 검증 불가`,
> `office 계약 대기`, `이미지 없음`) are kept verbatim in Korean because they are
> displayed literals. The four detail pages map as: Position Compare (`위치 비교`),
> Time-Series (`Time-Series`), Correlation / Distribution (`상관 / 분포`),
> Image Gallery (`이미지 갤러리`); Measurement Overview is `측정 개요`.

> **Status:** Design and implementation-plan draft complete; awaiting user review
> and implementation. This document is the implementation order and the verification
> gates — it does not change UI code by itself.

**Goal:** Keep `측정 개요` (Measurement Overview) as a fast summary/router while
re-shaping `위치 비교`, `Time-Series`, `상관 / 분포`, and `이미지 갤러리` into
engineering workbenches that are each useful for both single-MSR diagnosis and
multi-MSR comparison.

**Design:** [2026-07-16-skewvoir-analysis-drilldowns-design.md](../specs/2026-07-16-skewvoir-analysis-drilldowns-design.md)

**Research:** [wafer-analysis-method-research.md](../../issues/skewvoir/wafer-analysis-method-research.md), [analysis-drilldown-benchmark-research.md](../../issues/skewvoir/analysis-drilldown-benchmark-research.md)

**Architecture:** Keep the existing URL-driven workspace and `useSkewvoirAnalysis`.
Build the shared context/manifest layer first, and split per-page computation into
framework-free utilities. Raw data uses the `meas_hist` and `msr_file` contracts;
the office switch is handled at the existing `routes.py → data.py →
providers/mock.py|office.py` seam. Multi-MSR analysis uses only MSRs that pass the
compatibility gate, and baseline-based analysis is limited to descriptive mode until
a separate contract is ready.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, Nuxt UI, ECharts 6, Flask provider seam,
Node test runner, ESLint, Nuxt typecheck, markdownlint-cli2.

---

## 0. Implementation principles

1. `측정 개요` keeps loading exactly one focus MSR quickly. The initial Dashboard
   never pays a set fan-out because of detail comparison. Focus switching is
   allowed — what is banned is the set fan-out, not sequential single fetches.
2. Single-MSR and multi-MSR share the same menu but differ in question, grain, and
   empty state.
3. Multi-MSR computation is keyed on the *number of compatible MSRs*, not the
   *number selected*.
4. Do not merge overview, spatial, trend, relationship, and image evidence into a
   single health score.
5. The current mock `health` and the placeholder `spm_dict` are excluded from every
   judgment/validation path.
6. Each task closes in the order: framework-free computation test → component wiring
   → live evidence.
7. Changes that overlap the [wafer map enhancement design](../specs/2026-07-16-skewvoir-wafer-map-enhancement-design.md)
   in `WaferMap.vue`, `RadiusChart.vue`, `dashboard/RadiusPlot.vue`, and
   `dashboard/MeasurementPoints.vue` must be **landed first in Task 0**, and this
   plan starts on top of that result.

## 1. Stages and dependencies

```text
C0 analysis scope · compatibility · linked selection
 ├─ C1 Position Compare
 ├─ C2 Time-Series
 ├─ C3 Correlation / Distribution
 └─ C4 Image Gallery
       ↓
C5 Measurement Overview hand-off + cross-page QA
       ↓
C6 approved baseline / variance / advanced research (separate plan)
```

C1–C4 can be implemented independently once C0 is done. Do not change all four pages
at once — ship each page as a vertical slice.

## 2. Phase-1 completion boundary (mock backend)

Not every task in this plan can be considered "done" inside Phase 1 (offline mock).
The mock `msr_file` does not provide `site_layout_id`/layout hash,
coordinate-transform version, recipe revision, sequence timestamp, an approved
baseline, USL/LSL, image ROI/edge/line-profile, or a reference artifact. Tasks are
therefore classified as follows.

| Class | Tasks | State in Phase 1 |
| --- | --- | --- |
| Phase-1 buildable · verifiable | Tasks 1–5 (incl. 3b), 7, 9, 11, 13, 14 | The C0 shared layer, single-MSR diagnosis, review-queue gallery, and hand-off are live-verified on mock data. |
| Office-contract-gated | Tasks 6, 12 | Live-verifiable only after the canonical layout/coordinate and image-evidence contracts are connected. In Phase 1, build only the readiness `unavailable` placeholder. |
| Partially gated | Tasks 8, 10 | Descriptive run chart + tool/lot stratification (8) and MSR-grain pooled/stratified analysis (10) work on the mock. Control charts + recipe-revision facet (8) and capability/variance + spatial/same-site linking (10) are contract-pending. |

Office-contract-gated tasks do not finish their UI without a real contract. Declare
the entry gate under each task, and when the contract is missing, render only with a
clearly-labeled fixture and show `office 계약 대기` (awaiting office contract) on
screen. The Phase-1 shipping "done" bar is the buildable tasks plus the
mock-possible parts of the partially-gated tasks.

---

## Task 0: Land in-flight wafer-map work first (gating)

**Reason:** Uncommitted changes in the current worktree from the
[wafer map enhancement](../specs/2026-07-16-skewvoir-wafer-map-enhancement-design.md)
touch the same files as this plan. Land them first to avoid conflicts.

**Files (to land / confirm merged):**

- `front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue`
- `front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue`
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue`
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue`

**Gate:**

- [ ] Commit the wafer-map enhancement changes so `git status` is clean for the files above.
- [ ] Do not start Tasks 5/6/13 before it is clean.

---

## Task 1: Pin current behavior with characterization tests

**Files:**

- Read: `front-dev-home/app/composables/useSkewvoirRoute.ts`
- Read: `front-dev-home/app/composables/useSkewvoirWorkspace.ts`
- Read: `front-dev-home/app/composables/useSkewvoirAnalysis.ts`
- Read: `front-dev-home/app/components/ebeam/skewvoir/views/{Dashboard,PositionStack,TimeSeries,Correlation,Gallery}.vue`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/currentContracts.test.ts`

**Steps:**

- [ ] Pin the URL `msr`, `msrs`, `mp`, `view` parsing/serialization cases as test fixtures.
- [ ] Record current behavior of `msrs` order, focus MSR, the 30-item trend cap, and missing-MSR handling.
- [ ] Confirm the lazy-load invariant that `fetchMsrFiles` does not run when only the single Dashboard is open.
- [ ] Preserve `msr_file.rows` nullable `cd_value` and per-parameter units in the fixture.
- [ ] Note, via test name or comment, the current limits: Position Stack synthesizes chip coordinates directly, and Correlation/Gallery use only the focus file.
- [ ] Mark the "focus MSR only changes via search re-entry" current-behavior fixture as a test slated for update, because Task 3's `setFocusedMsr` intentionally supersedes it.

**Verify:**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run typecheck
```

**Commit:** `test(skewvoir): characterize analysis workspace contracts`

---

## Task 2: Add analysis truth types and the compatibility manifest

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/types.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/compatibility.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/compatibility.test.ts`
- Modify: `front-dev-home/app/composables/useMsrFileApi.ts`
- Modify: `back_dev_home/msr_file/providers/mock.py`
- Modify: `back_dev_home/msr_file/providers/office.py`
- Add: `back_dev_home/msr_file/tests/test_contract.py`
- Add: `docs/api-contracts/msr-file.yaml`

**Interfaces:**

- `AnalysisScope = 'single' | 'set'`
- `CompatibilitySignature`
- `CompatibilityGroup`
- `AnalysisManifest`
- `Readiness = { status: 'ready' | 'limited' | 'unavailable', reasons: string[] }`
- `CanonicalSiteKey`
- `ReferenceDescriptor`

**Steps:**

- [ ] Define the signature with recipe identity/revision, parameter/unit, method/object/kind, mag/vac/pixel, coordinate metadata, wafer size, and site-layout hash.
- [ ] Keep fields absent from current data as `unknown`. Do not treat two `unknown`s as equal.
- [ ] The mock provider explicitly returns the recipe/layout info it used to generate. Do not manipulate compatibility with hidden values just to make the screen match.
- [ ] Document the contract that the office adapter returns `NotImplemented` or a limited reason before canonical metadata is connected.
- [ ] `buildAnalysisManifest(focus, files, parameter)` computes included/excluded/group/readiness.
- [ ] Write a test that when layout differs, the readiness for multi-MSR delta, variability, and same-site gallery becomes `unavailable`.
- [ ] Write a test that when only some sites overlap, common coverage becomes `limited`.
- [ ] Add a backend contract test that the mock provider actually emits the declared signature fields, and that fields not in the contract (layout hash, recipe revision, sequence timestamp, etc.) do not appear in the response.
- [ ] Pin, via a backend test, that the office adapter returns `NotImplemented` or a limited reason before canonical metadata is connected.

**Acceptance:**

- Even when the user picks 12, the screen reproducibly explains `12 selected · 10 loaded · 8 compatible · 2 excluded`.
- Exclusion reason codes distinguish recipe/layout/unit/method/metadata-missing.

**Verify:**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run lint
npm --prefix front-dev-home run typecheck
python -m pytest back_dev_home/msr_file   # mock signature fields + office NotImplemented/limited contract
```

**Commit:** `feat(skewvoir): add analysis compatibility manifest`

---

## Task 3: Build the shared analysis context and shareable state

**Files:**

- Modify: `front-dev-home/app/composables/useSkewvoirRoute.ts`
- Modify: `front-dev-home/app/composables/useSkewvoirWorkspace.ts`
- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/workspace/AnalysisContextBar.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/workspace/ReadinessDrawer.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/Workspace.vue`

**Interfaces:**

- URL: `scope`, `site`, `ref`, `metric`, `grain`, `x`, `y`
- `analysis.manifest`
- `analysis.focusedSite`
- `analysis.reference`
- `analysis.setFocusedMsr(msr)`
- `analysis.setFocusedSite(siteKey | null)`

**Steps:**

- [ ] Keep `scope=single|set` separate from the selection count. In a multi-set, focus is the existing `msr`.
- [ ] Route parsing normalizes invalid queries to safe defaults and keeps opening existing shared links.
- [ ] Generalize `wantSet` from the `time-series|position-stack` hardcode to every detail page with `scope=set`. Exclude Dashboard.
- [ ] Show scope, focus, parameter, compatible/excluded count, reference provenance, and the set editor in the shared context bar.
- [ ] Show group composition, excluded MSRs and reasons, and per-capability ready/limited/unavailable in the readiness drawer.
- [ ] Reset the linked site when parameter or focus group changes and the site key is no longer valid.
- [ ] Keep the existing behavior of keyboard shortcuts 1–5 and the combobox guard.
- [ ] `setFocusedMsr(msr)` changes `msr` with the same router.replace pattern as `setView`/`setMsrs`/`setParam`, preserving `msrs`/`view`/`mp`. It adds no history entry, so Back still returns to search.
- [ ] On a focus switch, also rewrite `lot`/`eq`/`cap` from the new focus MSR's `meas_hist` row (`rowByMsr`) — LeftRail renders these URL fields verbatim, so no stale identity is left on screen. A deep-link MSR without a row keeps the existing values.
- [ ] Discard an in-flight focus fetch whose msr no longer equals the current URL `msr` at resolve time (stale-response guard). This race is real today: `fetchMsrFile` only dedupes in-flight requests and has no completed-response cache.
- [ ] When the focus file fails to load, keep the URL as truth and show a failure state with retry. Never keep rendering the previous MSR's data as if it were the new focus.
- [ ] `focusedSequence` reset and `mp` normalization are already handled by existing watchers — verify the behavior instead of re-implementing it.

**Acceptance:**

- A comparison set edited on Time-Series appears identically on Position/Correlation/Gallery.
- Opening the shared URL in a new tab restores scope, focus, parameter, site, and reference.
- No set batch request occurs when only Dashboard is open.
- `setFocusedMsr` adds no history entry and preserves `msrs`/`view`/`mp`.

**Commit:** `feat(skewvoir): add shared analysis context and readiness`

---

## Task 3b: Measurement Overview focus switcher chip strip

**Reason:** Even with multiple MSRs selected, today's Measurement Overview is not
aware of the comparison set, and there is no way to change the focus MSR inside
the workspace. As the first UI consumer of Task 3's `setFocusedMsr`, add a
comparison-set chip strip at the top of the overview that switches focus on click.
The overview still renders exactly one focus MSR at a time, so principle 0.1's
set-fan-out ban is not violated. Set add/remove stays the sole job of the shared
context bar's set editor; the chip strip is focus switching only.

**Files:**

- Add: `front-dev-home/app/components/ebeam/skewvoir/dashboard/FocusChipStrip.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Dashboard.vue`
- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts`

**Steps:**

- [ ] Render the chip strip only when `msrs` has 2+ members and view=dashboard. Chips follow the URL `msrs` order; labels come from the `meas_hist` row, falling back to the msr id when no row exists. Rendering chips requires no msr_file fetch.
- [ ] A chip click calls Task 3's `setFocusedMsr` and stays on the dashboard view.
- [ ] Resolve the focus file in order: session cache → `setFiles` → `fetchMsrFile`. The session cache is a `Map<msr, MsrFileResponse>` bounded at `TREND_LIMIT` (30).
- [ ] One switch causes at most one `GET /msr-file`, and the Dashboard never calls `fetchMsrFiles` (mind the mock 20-req/5s rate limit).
- [ ] Apply Task 3's stale-response guard so on rapid consecutive switches an earlier response never overwrites a later one.

**Acceptance:**

- The chip strip shows every member in URL `msrs` order and does not render when `msrs` has 1 or fewer members.
- A chip click changes only `msr` (plus that row's `lot`/`eq`/`cap`) via router.replace, preserving `msrs`/`view`/`mp`, with no history entry added.
- Switching to a never-seen MSR causes exactly one `GET /msr-file`, and no batch request ever occurs from the Dashboard (Task 1 invariant preserved).
- Returning to an already-viewed MSR in the same session renders from cache with zero network requests, and on rapid consecutive switches only the last-clicked MSR's data remains on screen.
- A switch resets `focusedSequence`, and on focus-file load failure the previous MSR's data is not kept as if current — a failure state with retry is shown (the clicked chip stays selected).

**Verify:**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run lint
npm --prefix front-dev-home run typecheck
```

**Commit:** `feat(skewvoir): add overview focus switcher chips`

---

## Task 4: Build the shared feature table and provenance

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/features.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/features.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/ProvenanceDrawer.vue`
- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts`

**Interfaces:**

- `MsrFeatureRow`
- `FeatureDefinition = { id, label, unit, grain, source, aggregation, family }`
- `DerivedValue<T> = { value, unit, n, missing, transform, reference, version }`
- `analysis.featureRows`
- `analysis.featureRegistry`

**Steps:**

- [ ] Make one row per MSR with level/spread/coverage/failure/spatial/fixed FDC/dynamic FDC summary.
- [ ] Reduce dynamic FDC to mean/std/range/robust slope/missing at sequence grain first.
- [ ] Preserve source, unit, aggregation, and missing for each feature.
- [ ] Do not auto-sum parameters of different units.
- [ ] Write a test that the current mock `health` and `spm_dict` never enter the feature registry.
- [ ] Build a shared contract so the `근거 보기` (view evidence) action on charts/tables opens the provenance drawer.

**Acceptance:**

- Time-Series and multi-MSR Correlation share the same feature values without recomputing.
- Every exportable derived value is traceable to raw source and transform.

**Commit:** `feat(skewvoir): build grain-safe MSR feature table`

---

## Task 5: Position Compare, single MSR — spatial diagnosis

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/spatial.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/spatial.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SpatialLayerMap.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/RadialProfile.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SectorProfile.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SiteEvidenceDrawer.vue`
- Modify (branch-by-abstraction): `front-dev-home/app/components/ebeam/skewvoir/views/PositionStack.vue`

**Steps:**

- [ ] Do not delete the existing composite-mean view immediately; attach the new single-MSR workbench behind a flag/condition so the current screen keeps working until verified.
- [ ] Define the raw, median-centered, residual, and failure layers.
- [ ] Compute per-radius-bin median/spread/N and a verified notch-based sector summary.
- [ ] When coordinate readiness is insufficient, keep only the raw layer and table and show the reason.
- [ ] Provide a sequence scan-path overlay to check whether space and measurement order are confounded.
- [ ] Link map/profile/table/SEM preview by `focusedSite`.
- [ ] The Answer strip shows center-edge delta, direction contrast, largest local residual, and coverage as separate evidence.
- [ ] Pin a test that a single MSR does not compute wafer-to-wafer σ.

**Live verification:**

- Switch raw→centered→failure layers on both CD-SEM and HV-SEM.
- Clicking a map site moves profile/table/SEM to the same site.
- On a fixture with coordinate metadata removed, the sector becomes `평가 불가` (not evaluable).

**Commit:** `feat(skewvoir): turn position view into single-MSR spatial diagnosis`

---

## Task 6: Position Compare, multi MSR — reference/delta workbench

> ⚠ **Office-contract-gated (excluded from Phase 1).** Entry gate: the canonical
> layout/coordinate-identity contract (§10.2 PhysicalSiteKey) must be connected in
> the backend. In the Phase-1 mock, layout is `unknown`, so do not build the
> delta/variability map — show only readiness `unavailable` and the required contract.

**Files:**

- Extend: `front-dev-home/app/utils/skewvoirAnalysis/spatial.ts`
- Extend: `front-dev-home/app/utils/skewvoirAnalysis/spatial.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SpatialComparison.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SiteHistory.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/WaferSmallMultiples.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/PositionStack.vue`

**Steps:**

- [ ] Compute the leave-focus-out per-site median reference, focus delta, site variability, and coverage.
- [ ] Write a test that excludes the focus from the reference computation.
- [ ] MSRs with no common sites are not silently dropped from the computation — send them to the manifest exclusion.
- [ ] Make reference and delta the first screen and demote the current Composite Mean to a secondary layer.
- [ ] Every comparison map supports pin scale.
- [ ] Link the selected site's MSR history and the same-site Gallery hand-off.
- [ ] Show center-corrected RMSE/correlation only as `pattern similarity` — do not generate a fault label.

**Acceptance:**

- Changing focus recomputes the reference, with no delta-stuck-at-0 bug.
- The variability tooltip shows σ/MAD together with the per-site valid MSR N.
- A layout-mismatched set does not build a false alignment map.

**Commit:** `feat(skewvoir): add compatible-set spatial comparison`

---

## Task 7: Time-Series, single MSR — link sequence and dynamic FDC

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/sequence.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/sequence.test.ts`
- Reuse/Modify: `front-dev-home/app/components/ebeam/skewvoir/FdcSequenceTrend.vue`
- Reuse/Modify: `front-dev-home/app/components/ebeam/skewvoir/FdcScatter.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceEventLane.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/TimeSeries.vue`

**Steps:**

- [ ] In single scope, change the title and X axis to `측정 순서 (Sequence)`.
- [ ] Show CD and dynamic FDC as stacked panes with a shared cursor.
- [ ] Compute start/end/range/robust slope/missing and label the unit `per sequence`.
- [ ] Place failure/image/alignment evidence in the sequence event lane.
- [ ] Link the sequence cursor to the wafer scan path and `focusedSite`.
- [ ] Do not merge CD/FDC of different units onto one Y axis.
- [ ] Mark in the pane meta that, in the home mock, CD and dynamic FDC are coupled through the shared `health` scalar — show `데모 데이터 · 방법 검증 불가` (demo data · method not validatable).
- [ ] Write a test that no per-second slope or time-lag UI appears when there is no sequence timestamp.

**Acceptance:**

- One cursor makes CD, FDC, wafer position, and image point to the same sequence.
- An MSR without dynamic FDC shows only the CD sequence and displays `FDC 없음` (no FDC) with the reason.

**Commit:** `feat(skewvoir): add single-run sequence and FDC workbench`

---

## Task 8: Time-Series, multi MSR — run chart and event context

> ⚠ **Partially gated.** The descriptive run chart and tool/lot stratification are
> built and verified on the Phase-1 mock. Control charts (I-MR/EWMA/CUSUM) and the
> recipe-revision facet have no approved-baseline / recipe-revision contract, so
> keep them as disabled readiness only and exclude them from the Phase-1 done bar.

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/trend.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/trend.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/MetricPicker.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/RunChart.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/EventLane.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/StratifiedTrends.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/TimeSeries.vue`

**Steps:**

- [ ] Organize the metric picker into level/spread/completeness/spatial/tool-evidence families.
- [ ] Compose the default screen as four lanes — CD level, uniformity (WCDU·MAD), measurement quality, tool context — linked by the same time cursor.
- [ ] The metric picker only swaps each lane's representative metric; it does not merge evidence families into one score.
- [ ] Provide tool/lot/recipe-revision/maintenance-regime color and facet.
- [ ] Visually preserve real timestamps and irregular elapsed gaps.
- [ ] Rename the current peer `%/σ` control to `선택 집합 탐색 편차` (selection-set exploratory deviation).
- [ ] When there is no approved baseline, do not hide the I-MR/EWMA/CUSUM control — explain it as disabled readiness.
- [ ] Separate theme tokens so spec/engineering/control limits do not share the same style.
- [ ] Clicking a point changes the focus MSR and passes state to other pages.

**Deferred in this task:**

- The approved baseline registry and control-limit computation.
- The real pre/during/post event-time join from the hardware service.
- Using automatic change-points for official judgment.

**Acceptance:**

- Changing the selection set does not auto-generate new limit lines that look like official control limits.
- Faceting by tool lets you see the difference between the pooled trend and each tool's trend.
- From an MSR point you can navigate to raw feature provenance and Measurement Overview.

**Commit:** `feat(skewvoir): add stratified multi-MSR run charts`

---

## Task 9: Correlation / Distribution, single MSR — exact-pair factor explorer

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/relationships.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/QueryBuilder.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/CorrelationScatter.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/DistributionChart.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/RelationshipSummary.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/PairedEvidenceTable.vue`
- Modify (branch-by-abstraction): `front-dev-home/app/components/ebeam/skewvoir/views/Correlation.vue`

**Steps:**

- [ ] Keep the existing focus-only scatter/distribution view until verified, and attach the new exact-pair explorer behind a flag.
- [ ] Allow only canonical-site (PhysicalSiteKey) or same-sequence exact joins. For different parameters such as CD↔FDC and X↔Y, join on the PhysicalSiteKey with parameter removed.
- [ ] Compute Pearson r, Spearman ρ, pair N, missing N, and constant-variable readiness.
- [ ] The active query updates scatter, marginal distribution, group distribution, and evidence table together.
- [ ] Add ECDF as a default comparison option beside the histogram, and show raw points or N on top of box/violin.
- [ ] Provide radius/sector groups only when coordinate readiness passes.
- [ ] Mark in the chart meta that CD↔dynamic FDC is a same-MSR+sequence join.
- [ ] Because CD and dynamic FDC are coupled via the shared `health` scalar in the home mock, add a `데모 데이터 · 방법 검증 불가` mark to the CD↔FDC correlation chart on this data.
- [ ] Always show the phrase `연관이며 원인 증명이 아님` (association, not proof of cause) on correlations.

**Acceptance:**

- When pair count is 0 or one axis is constant, it is not evaluable — not `r=0`.
- Missing rows of a different parameter are not mis-paired by index order.
- Clicking a scatter point links the focused site and SEM preview.

**Commit:** `feat(skewvoir): add paired-site relationship explorer`

---

## Task 10: Correlation / Distribution, multi MSR — stratified feature analysis

> ⚠ **Partially gated.** The MSR-grain pooled/stratified relationship is built and
> verified on the Phase-1 mock. Cp/Cpk (spec contract), variance component, and the
> spatial/same-site linking that needs the PhysicalSiteKey are contract-pending and
> excluded from the Phase-1 done bar.

**Files:**

- Extend: `front-dev-home/app/utils/skewvoirAnalysis/relationships.ts`
- Extend: `front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/FeatureMatrix.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/StratifiedEstimate.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/GroupDistribution.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Correlation.vue`

**Steps:**

- [ ] Fix grain to MSR and use the feature row from Task 4.
- [ ] Show the overall pooled scatter and per-tool estimates side by side.
- [ ] Choose color/facet from tool, lot, maintenance regime, recipe revision.
- [ ] Selecting a correlation-matrix cell drills down into an X/Y query.
- [ ] The discovery matrix shows a multiple-comparison warning and feature/missing counts.
- [ ] Without authoritative spec metadata, do not provide Cp/Cpk or out-of-spec counts.
- [ ] Variance component provides only a readiness placeholder and defers to the separate C6 plan.
- [ ] Home-mock CD↔FDC results show the `데모 데이터 · 방법 검증 불가` mark.

**Acceptance:**

- On a fixture where the pooled and per-tool relationships are opposite, both are shown and not summarized into one.
- The number of site rows does not inflate the MSR-grain N.
- The feature tooltip has source, unit, aggregation window, and missing.

**Commit:** `feat(skewvoir): add stratified MSR feature analysis`

---

## Task 11: Image Gallery, single MSR — priority review queue

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/gallery.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/gallery.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/ReviewFilters.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/EvidenceCard.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/ImageEvidenceDrawer.vue`
- Modify (branch-by-abstraction): `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue`

**Steps:**

- [ ] Keep the existing filename grid until verified, and attach the new review-queue behind a flag.
- [ ] Classify image rows by failure, residual, vendor-score-monitor, and sequence reason. Use the `abnormal/watch` site verdict as a classification basis **only when judgment provenance is provided**, and never derive it from the mock `health` (§0.5).
- [ ] Default sort is failure → residual magnitude → sequence. Insert abnormal/watch right after failure only when verdict provenance exists.
- [ ] Vendor score creates only a monitoring badge and is not included in the verdict reason.
- [ ] Show chip/MP, sequence, parameter/value/unit, residual, and reason on the card.
- [ ] Apply a virtualized/lazy grid and per-image retry.
- [ ] In the viewer, provide pan/zoom, a physical scale bar, keyboard prev/next, metadata, and wafer-position navigation.
- [ ] If the backend provides ROI/edge/CD gauge/line profile with an algorithm version, show the measurement-evidence layer; otherwise hide the capability and show `원본 image만 제공됨` (only the original image is provided).
- [ ] Provide charging/contrast, focus/astigmatism, image drift, contamination/repeat exposure, edge algorithm, and pixel calibration as `artifact 의심` (suspected artifact) review tags separate from the pattern verdict.
- [ ] Map/table/gallery share the focused site.

**Acceptance:**

- The `이상·실패 우선` (abnormal/failure first) filter shows only images that have a basis.
- Even with no image, the site evidence row does not disappear and shows `이미지 없음` (no image).
- A single failed image URL does not block the whole Gallery loading state.

**Commit:** `feat(skewvoir): turn gallery into visual evidence queue`

---

## Task 12: Image Gallery, multi MSR — same-site filmstrip

> ⚠ **Office-contract-gated (excluded from Phase 1).** Entry gate: the
> PhysicalSiteKey (§10.2) and the image acquisition/scale metadata contract are
> required. In the Phase-1 mock the canonical site cannot be determined, so do not
> build the filmstrip — show readiness `unavailable`.

**Files:**

- Extend: `front-dev-home/app/utils/skewvoirAnalysis/gallery.ts`
- Extend: `front-dev-home/app/utils/skewvoirAnalysis/gallery.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/SameSiteFilmstrip.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/PinnedComparison.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue`

**Steps:**

- [ ] Group compatible-MSR images by canonical site in time order.
- [ ] Pin up to 4 focus/reference/before-after images to view at the same scale.
- [ ] Show CD/delta/tool/lot/timestamp/mag/vac/pixel on each frame.
- [ ] Leave a missing image as an empty cell.
- [ ] Show a visual compatibility warning when magnification/pixel/method differ.
- [ ] Do not offer a pixel-diff action without registration metadata.
- [ ] When physical pixel scale differs, do not directly compare by same-size thumbnails alone — show a calibration warning.
- [ ] Bidirectionally link the Position Compare selected site and the Gallery filmstrip.

**Acceptance:**

- The same `chip_number` from a different layout is not merged into the same site.
- Filmstrip order is the real timestamp and does not depend on the current set-selection order.
- Acquisition-condition differences are immediately visible in the pinned-image comparison.

**Commit:** `feat(skewvoir): add same-site historical image comparison`

---

## Task 13: Wire the evidence hand-off from Measurement Overview

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Dashboard.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/overview/StatBar.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/ParamNav.vue`
- Modify as needed: `front-dev-home/app/components/ebeam/skewvoir/dashboard/{WaferMap,RadiusPlot,MeasurementPoints,SemImage,Distribution}.vue`

**Steps:**

- [ ] Do not add detail mini-charts to the overview.
- [ ] Generate the `공간 pattern 자세히` (spatial pattern detail), `측정 순서와 FDC` (sequence and FDC), `짝지은 값` (paired values), and `검토할 이미지` (images to review) hand-offs only from confirmed facts.
- [ ] Pass view, parameter, focused site/sequence, X/Y query, and filter in the hand-off.
- [ ] For a detail page whose data is not ready, show the reason instead of a CTA.
- [ ] Keep the linked selection and the current compact no-page-scroll layout. Task 3b's chip strip also fits inside this layout.

**Acceptance:**

- Navigating from an overview wafer site to Gallery selects the same site and parameter.
- Navigating from sequence evidence to Time-Series restores the single-scope sequence cursor.
- The overview's initial load request count and layout height are identical to before the detail-page rework. A chip switch adds at most one msr_file request (zero on a cache hit).

**Commit:** `feat(skewvoir): route overview evidence into drilldowns`

---

## Task 14: Verify cross-page UX, accessibility, performance, and export

**Files:**

- Modify: `front-dev-home/app/utils/echartsThemes.ts`
- Modify: `front-dev-home/app/utils/chartPalette.ts`
- Add: `front-dev-home/tests/e2e/skewvoir-analysis-workflow.spec.ts` (or the current E2E-convention path)
- Modify: related view/component tests
- Update: user docs and the API contract

**Steps:**

- [ ] Separate the color/dash tokens of spec/engineering/control/reference lines.
- [ ] Provide keyboard focus, an accessible name, and a text summary for charts.
- [ ] Distinguish states with symbol/line style beyond red/green.
- [ ] Verify desktop keeps panel-internal scroll inside the viewport, and mobile uses summary-first + a full-screen workbench.
- [ ] Measure the set batch-request count, image lazy load, chart-point cap, and progressive rendering.
- [ ] Include scope, grain, included/excluded MSR, unit, transform, reference, baseline/version, and missing in the export.
- [ ] Verify all CD-SEM/HV-SEM, single/set, and complete/missing/incompatible fixtures.

**Quality gate:**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run lint
npm --prefix front-dev-home run typecheck
npm --prefix front-dev-home run build
npx markdownlint-cli2 \
  docs/superpowers/specs/2026-07-16-skewvoir-analysis-drilldowns-design.md \
  docs/superpowers/plans/2026-07-16-skewvoir-analysis-drilldowns.md \
  docs/issues/skewvoir/analysis-drilldown-benchmark-research.md
git diff --check
```

**Live scenarios:**

1. Single MSR → Measurement Overview → Position Compare → same-site Gallery.
2. Single MSR → sequence/FDC → paired CD/FDC scatter → image.
3. Multi MSR → compatibility exclusion → focus delta → MSR run chart.
4. Multi MSR → pooled vs tool-stratified relationship → focus MSR evidence.
5. Missing coordinate/layout/image/FDC and the no-approved-baseline state.

**Commit:** `test(skewvoir): verify analysis drilldown workflow`

---

## Task 15: Items to split into a separate follow-up plan

The following are not implemented prematurely just to create a UI placeholder.

- Approved historical baseline registry, versioning, and review/contamination policy.
- Offline false-alarm / shift-detection validation of I-MR/EWMA/CUSUM.
- Hardware BSM/Reso/MDC/SCE/BM·PM event-time join.
- Tool/lot/wafer/site variance component and the identifiability gate.
- Reference-artifact-based tool-to-tool matching and metrology/process bias decomposition.
- Spatial signature library and engineer labeling workflow.
- PCA/MSPC, virtual metrology, dynamic sampling.
- Image registration, edge/ROI · gray-level line-profile office contract, and similarity model.

Each requires real office history and a separate acceptance dataset, so proceed as
an independent spec/plan after C0–C5 ship.

---

## Self-Review

**Design coverage:**

- Design §2–§4 progressive disclosure, adaptive scope, context bar, and linked selection are reflected in Tasks 2–4.
- Design §5 Position Compare is split into single/multi vertical slices in Tasks 5–6.
- Design §6 Time-Series splits sequence and real-time run in Tasks 7–8.
- Design §7 Correlation / Distribution splits exact site pair and MSR feature grain in Tasks 9–10.
- Design §8 Gallery splits into review queue and same-site filmstrip in Tasks 11–12.
- Design §9–§11 grain, URL, provenance, and statistical integrity are the gates in Tasks 2–4 and 14.
- Design §13 advanced features are explicitly moved to Task 15.

**Current-code alignment:**

- Keep `useSkewvoirAnalysis`'s Dashboard single fetch and lazy set fetch.
- Reuse the existing `fixed_fdc`, `dynamic_fdc`, `fdc_params`, and image-URL seam.
- Extend, not replace, the existing `focusedSequence`, `activeParam`, and URL `msrs`.
- Unify first, in C0, the facts that `Correlation.vue`/`Gallery.vue` are focus-only and that only Position/Time-Series load the set.
- Backend changes do not exceed the existing `msr_file/routes.py → data.py → providers` seam.

**Primary risks:**

| Risk | Gate |
| --- | --- |
| Wrongly merging same-named recipe/layout | compatibility signature + unknown-safe policy |
| Using a single site as an independent run | explicit grain + MSR feature row |
| Generating control limits from a selection set | baseline readiness + descriptive default |
| Mistaking a mock correlation for a validation result | mock label + method-validation ban |
| Gallery exploding request/render | lazy original + virtual grid + batch context |
| Overview becoming heavy again | Dashboard set-fetch-ban characterization test + chip switch is single-fetch + cache |
| Conflict with current wafer-map work | re-check worktree at Task 0 / implementation start |

The completion condition of this plan is not that four pages get charts, but that
**each page answers one engineering question and every answer keeps its
compatibility, grain, N, missing, reference, and raw evidence.**
