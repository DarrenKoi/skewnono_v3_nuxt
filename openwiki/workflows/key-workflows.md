---
type: Workflow Guide
title: Key Application and Engineering Workflows
description: End-to-end paths for Device Statistics, recipe and hardware operations, live alarms, Skewvoir, AFM, chat, and adding or migrating provider-backed SKEWNONO features.
resource: front-dev-home/app/pages
tags: [workflows, device-statistics, hardware, live-alarm, skewvoir, mag-pixel, afm, chat]
---

# Key workflows

## Device Statistics

### User path

1. Open `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/index.vue` and select lots within one fab.
2. Carry the lot cart into `comparison.vue` or open a focused `profile.vue`.
3. Choose the page-wide recipe bucket and inspect lot counts, parameter distributions, trends, recipe rows, and parameter detail.
4. Apply rules from `measurement-rules.vue`; `app/utils/ruleEngine.ts` resolves parameter caps and lot-health rollups.

R3 selection is organized by product category and lot; M-fab selection uses technology. The selection set is intentionally bounded because unfiltered recipe-statistics and parameter responses can be very large.

### Code path

```text
pages/.../device-statistics/*.vue
  -> useDeviceStatisticsApi / useRecipeStatisticsApi
  -> /api/cdsem/device-statistics/*
  -> back_dev_home/ebeam/cdsem/device_statistics/routes.py
  -> data.py
  -> selected provider
```

`useDeviceCart.ts`, `useDevicePresets.ts`, and preferences composables coordinate selection state. Rule reads flow through `useMeasurementRulesApi.ts` to `/api/cdsem/device-statistics/rules?fac_id=...`; `fac_id` is the rule contract's deliberate name for this feature axis. Write/history/rollback methods are not yet implemented. The [domain guide](../domain/concepts.md#device-statistics-and-measurement-governance) defines the non-negotiable lot, bucket, rule, and health semantics.

When changing this flow, run `tests/test_recipe_analytics_home.py`, the backend feature contract tests, `ruleEngine.test.ts`, and device-drill utility tests.

## Recipe and hardware operations

Recipe search loads the daily Redis-backed catalog, ranks exact matches before prefix, substring, and unordered AND-token matches, and preserves search/page state in the URL. When an eligible settled query has no Redis matches, `RecipeSearchView.vue` waits 600 ms and uses `/api/meas-hist/search`'s validated, composite-paginated distinct `recipe_names` snapshot as an OpenSearch fallback. Redis always wins and cancels fallback results; incomplete snapshots cannot masquerade as a definitive empty result. Fallback entries retain `source: 'opensearch'` in working sets and support selection, lateral expansion, and measurement history, but not recipe open or compare; a mixed set uses the intersection of those capabilities (`app/utils/recipeSearchMatch.ts`, `recipeSelection.ts`, and `recipeView.ts`).

Opening a Redis-origin recipe locates its newest usable measurement-history document, downloads the corresponding `.idp` from the measuring tool, and parses measurement-point, alignment-point, and parameter/image tables through the [FTP integration](../integrations/integration-points.md#ftp-ingestion). In `idp_image_info`, `Addressing`, `Mother_Para`, and `dnumber_removed` are booleans: `Mother_Para=true` marks that row's own parameter as a mother, while `dnumber_removed=true` means its data is suppressed from legacy delivery. Alignment images and AMP details remain synthetic in office mode, and compare remains mock-backed (`back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md`, `docs/datatables/recipe_idp.txt`).

The hardware page dispatches each tab through `back_dev_home/ebeam/hitachi/hardware/providers/<tab>/`. BM/PM combines past `fab_inform_notes` events with future `tool_maintenance_plan` work; FDC groups SPM channels into measurement cycles and offers multiple LaserPower interpretations; sharpness coordinates condition selection, scalar trends, and timestamp-specific 360-degree profiles. BSM normalizes beam-shape profiles and category labels. SCE compares the selected tool with siblings and trends numeric settings plus coefficient indices; its Coefficients overlay collapses consecutive collection documents with structurally identical `Coefficients` arrays into one settings revision, keeps reverted curves as new revisions, and defaults the newest three revisions while allowing recent/all/manual selection. MDC/SCE picker bulk actions apply only to the current case-insensitive search matches: select unions matches with the existing set, while clear subtracts them. Reso Center plots flat center fields with the visible Best/IS-center gap equal to `ResoDelta`. These user views [depend on exact office mappings](../integrations/integration-points.md#hardware-opensearch-adapters); tracked MDC and Reso Center reconstructions now require deliberate diff/merge into any office-local adapters and real-source verification, while a missing nested adapter still falls back to that tab's mock.

Lateral-recipe readiness has a cross-feature invariant: a tool observed executing the exact recipe in recent measurement history is ready even when the IDP version document omits it. Explicit IDP version assignment still wins, and the office adapter uses the newest discovered version only for measured tools absent from all assignments (`back_dev_home/ebeam/hitachi/lateral_recipe/providers/office_example.py`).

## Live alarm board

The CD-SEM and HV-SEM routes render `LiveAlarmView.vue`, which polls `GET /api/<tool_slug>/live-alarm?fab_name=...` every 15 seconds with jitter. The server returns the complete deduplicated 10-minute board, so the client replaces rather than accumulates events, pauses while hidden, refreshes on visibility return, and keeps the last good board until three consecutive request failures. First load is treated as already seen; later arrivals separately drive a persistent title count and an eight-second row highlight (`useLiveAlarmFeed.ts`).

The Flask reader and mock provider are implemented. Office operation [depends on the Redis writer integration](../integrations/integration-points.md#live-alarm-writer-and-reader): an external scheduler must run the portable writer every 15 seconds, while Flask reads events and heartbeat state through a local `providers/office.py`. Feed status is `live`, `stale`, or `not_configured`; failed fab polls do not advance their heartbeat. Deployment and diagnosis are in the [operations runbook](../operations/runbook.md#live-alarm-office-deployment).

## Skewvoir search and analysis

### User path

1. Search measurement history by fab, model, equipment, recipe, lot, MSR, text, and date.
2. Open one MSR as focus or build an explicit comparison set.
3. Inspect overview, position stack, FDC analysis, time series, correlation, and gallery modes.
4. Share the URL to preserve focus, set, parameter, site, reference, metric, grain, FDC axis, chart axes, and gallery filters.

`useMeasHistSearch.ts` and `useMeasHistFacets.ts` drive discovery. Search state is SPA-session scoped and separately keyed for the CD-SEM and HV-SEM landing routes: returning from analysis restores the query, filters, loaded rows, and paging state, while a full reload starts clean. The route key isolates UI sessions but does not constrain the OpenSearch query—only the category filter does—and superseded search or load-more responses cannot overwrite the current session. `useSkewvoirRoute.ts` owns URL serialization, while `useSkewvoirAnalysis.ts` fetches and caches focus/set data with stale-response protection. FDC analysis is intentionally a single-MSR, sequence-order view; Time-Series is the multi-MSR/set trend view. The default FDC axis contains only sequences for the active parameter, while `fdcaxis=all` opts into the whole-MSR union. Failed measurement rows remain visible as CD gaps with aligned FDC state, and row/`dynamic_fdc` count mismatches surface as integrity warnings rather than being hidden.

### Data path

```text
Search and facets
  -> /api/meas-hist/*
  -> measurement parent metadata

Focus and comparison analysis
  -> /api/msr-file/<id> or POST /api/msr-files
  -> detailed rows, summaries, FDC/alignment, and geometry

Measurement image API
  -> /api/msr-images and /api/msr-image
  -> tool source through back_dev_home/msr_image/
  -> disk cache in mock mode or MinIO cache in office mode
```

Bulk detail loading is capped at 200 and avoids consuming one rate-limit slot per selected MSR. Dashboard mode fetches the focus record; set views lazily batch the curated set. Public `fail_ratio` is always a 0–100 percentage: mock derives it from counts, while office preserves the percentage already computed by OpenSearch. `msr_file` resolves `eqp_ip` from the MSR's parent measurement document and returns it with `class_name` and `msr`, so image addressing works for search hits and shared links that are absent from the cached landing list; a loaded measurement-history row is only a frontend fallback. Gallery and evidence views use `useMsrImageApi.ts` to list and fetch per-MSR images, expose condition text, start download-all, poll progress, surface listing/per-file failures, and offer TIFF originals as downloads. The limiter-exempt Blueprint validates tool IP/subnet and safe path segments; its tracked office adapter and optional Redis job store are described in the [integration boundary](../integrations/integration-points.md#measurement-image-delivery-and-cache).

Wafer position logic keeps physical stage coordinates centered on the wafer while `map_offset` shifts only die-indexed geometry: die centers, boundaries, and labels. `map_origin` is informational because `chip_number` is already origin-relative. Invalid pitch or coordinates remain unplaceable rather than being guessed as die `(0,0)` (`app/utils/waferGeometry.ts`, `waferDieGrid.ts`, and `waferAxis.ts`).

The [review model](../domain/concepts.md#skewvoir-review-model) requires official cohorts to remain distinct from exploratory sets. Office `msr_file` data must still establish stable revision and compatibility metadata before cross-MSR spatial comparisons can be considered authoritative; image delivery has moved out of `msr_file` into its own integration boundary.

## CD-SEM Mag/Pixel setup

The `/mag-pixel` guide starts with a labeled CG example and recalculates as the engineer chooses a CG/GT series, CD, pitch, pattern count, edge margin, and minimum pixels per CD. `app/utils/magPixel.ts` first derives the required FOV, chooses the highest discrete magnification that still contains the pattern, then chooses the smallest pixel setting that satisfies the provisional sampling threshold. Invalid or cleared fields remain unevaluated, pitch must exceed CD, and the unverified GT range above 500K stays visibly marked as assumed.

`SemSimulation.vue` shows both the full FOV and a fixed-physical-width edge zoom. The zoom compares real pixel samples without stretching cells or changing the physical edge width, so increasing the pixel setting changes sample density rather than pretending to change the specimen. Keep this workflow aligned with the [metrology constraints](../domain/concepts.md#cd-sem-magpixel-setup) and Skewvoir's gallery-scale calculation. Changes should run `app/utils/magPixel.test.ts`, including FOV, recommendation, orientation, invalid-input, and edge-sampling cases, followed by frontend typecheck and a browser check of cleared inputs and assumption badges.

## AFM detail and comparison

The implementation path below is currently gated off: `useAfmAvailability.ts` sets `AFM_ENABLED = false`, and `afm-hidden.global.ts` redirects `/afm/*` to the home page. When enabled:

1. Enter `pages/afm/index.vue`, choose a fab/tool, and search files through `pages/afm/[tool]/index.vue`.
2. Open `[filename].vue` for measurement metadata, point table, scatter, heatmap, histogram, profile, and captured analysis images.
3. Export CSV/charts/images or add files to `useAfmCart.ts`.
4. Open `see-together.vue` for multi-measurement analysis.

`useAfmDetailApi.ts` dispatches to `back_dev_home/afm/routes.py` through its provider seam. The active API retains legacy aliases and duplicate naming in some payloads for migration compatibility. Reset component-local pagination/filter state when the measurement changes; recent fixes explicitly addressed stale points-table pages.

The former standalone `afm_data_platform/` was removed after this migration completed. Use `docs/afm-migration-plan.md` and targeted Git history when old data or endpoints matter; application changes belong in the integrated paths mapped in the [source map](../source-map.md#active-application).

## Chat

1. Select a model and optional system prompt before thread creation in `pages/chat.vue`.
2. `useChatApi.ts` creates/updates per-user threads and sends messages.
3. `back_dev_home/chat/routes.py` delegates persistence through `data.py` and completions through `llm.py`.
4. Before calling the configured OpenAI-compatible `/chat/completions` endpoint, `guard.py` blocks known public LLM hosts in office provider mode.

Home persistence is SQLite with a 30-day thread lifetime. In office mode, configure an approved internal `CHAT_BASE_URL`; a blocked destination returns `403 egress_blocked`, leaves the user message persisted for retry, and writes no assistant message. Token/configuration details belong in trusted environment configuration and must not be documented as values. The current path sends conversation history directly; [integration points](../integrations/integration-points.md#llm-gateway) defines the egress boundary and marks retrieval/tool calling as future work.

## Add or migrate a feature

1. Decide scope: shared Hitachi feature, CD-SEM/HV-SEM-specific feature, or top-level product feature.
2. Create `routes.py` exporting globally unique `bp`, `data.py`, `contracts.py`, `providers/mock.py`, and tracked `providers/office_example.py`.
3. Keep route validation and HTTP behavior in `routes.py`; keep source selection in `data.py`; keep transport queries and normalization in providers. At the office, use `scripts.setup_office_adapters` or targeted `scripts.sync_office_adapters` rather than blindly overwriting ignored `office.py`; stub and locally edited copies require deliberate handling.
4. Restart Flask after adapter changes, add the frontend composable and page/component consumers against `/api` without environment branches, and confirm actual selection through `/api/health/providers`.
5. Add provider contract tests and representative route tests. For office migration, run the same gate with the feature override set to `office` and exercise representative real data on-site.
6. Update API contracts and migration notes, then follow [operations](../operations/runbook.md) and [testing guidance](../testing/guidance.md).

Blueprint registration is automatic. Verify application startup because discovery imports every route module. Prefer a clear `NotImplementedError` over an office adapter returning plausible empty data.
