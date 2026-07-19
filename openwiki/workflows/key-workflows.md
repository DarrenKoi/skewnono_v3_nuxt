---
type: Workflow Guide
title: Key Application and Engineering Workflows
description: End-to-end paths for Device Statistics, Skewvoir, AFM, chat, and adding or migrating provider-backed SKEWNONO features.
resource: front-dev-home/app/pages
tags: [workflows, device-statistics, skewvoir, afm, chat]
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

`useDeviceCart.ts`, `useDevicePresets.ts`, and preferences composables coordinate selection state. Rule reads flow through `useMeasurementRulesApi.ts`; write/history/rollback methods are not yet implemented. The [domain guide](../domain/concepts.md#device-statistics-and-measurement-governance) defines the non-negotiable lot, bucket, rule, and health semantics.

When changing this flow, run `tests/test_recipe_analytics_home.py`, the backend feature contract tests, `ruleEngine.test.ts`, and device-drill utility tests.

## Skewvoir search and analysis

### User path

1. Search measurement history by fab, model, equipment, recipe, lot, MSR, text, and date.
2. Open one MSR as focus or build an explicit comparison set.
3. Inspect overview, position stack, time series, correlation, and gallery modes.
4. Share the URL to preserve focus, set, parameter, site, reference, metric, grain, axes, and gallery filters.

`useMeasHistSearch.ts` and `useMeasHistFacets.ts` drive discovery. `useSkewvoirRoute.ts` owns URL serialization, while `useSkewvoirAnalysis.ts` fetches and caches focus/set data with stale-response protection.

### Data path

```text
Search and facets
  -> /api/meas-hist/*
  -> measurement parent metadata

Focus and comparison analysis
  -> /api/msr-file/<id> or POST /api/msr-files
  -> detailed rows, summaries, FDC/alignment, geometry, and images
```

Bulk detail loading is capped at 200 and avoids consuming one rate-limit slot per selected MSR. Dashboard mode fetches the focus record; set views lazily batch the curated set. MSR images are exempt from the general API limiter because galleries fan out many deterministic requests.

The [review model](../domain/concepts.md#skewvoir-review-model) requires official cohorts to remain distinct from exploratory sets. Office `msr_file` data must eventually provide stable layout/revision/coordinate/timestamp metadata before cross-MSR spatial comparisons can be considered authoritative.

## AFM detail and comparison

1. Enter `pages/afm/index.vue`, choose a fab/tool, and search files through `pages/afm/[tool]/index.vue`.
2. Open `[filename].vue` for measurement metadata, point table, scatter, heatmap, histogram, profile, and captured analysis images.
3. Export CSV/charts/images or add files to `useAfmCart.ts`.
4. Open `see-together.vue` for multi-measurement analysis.

`useAfmDetailApi.ts` dispatches to `back_dev_home/afm/routes.py` through its provider seam. The active API retains legacy aliases and duplicate naming in some payloads for migration compatibility. Reset component-local pagination/filter state when the measurement changes; recent fixes explicitly addressed stale points-table pages.

The standalone `afm_data_platform/` may explain old data and endpoints, but application changes should target the integrated paths mapped in the [source map](../source-map.md#active-application).

## Chat

1. Select a model and optional system prompt before thread creation in `pages/chat.vue`.
2. `useChatApi.ts` creates/updates per-user threads and sends messages.
3. `back_dev_home/chat/routes.py` delegates persistence through `data.py` and completions through `llm.py`.
4. Before calling the configured OpenAI-compatible `/chat/completions` endpoint, `guard.py` blocks known public LLM hosts in office provider mode.

Home persistence is SQLite with a 30-day thread lifetime. In office mode, configure an approved internal `CHAT_BASE_URL`; a blocked destination returns `403 egress_blocked`, leaves the user message persisted for retry, and writes no assistant message. Token/configuration details belong in trusted environment configuration and must not be documented as values. The current path sends conversation history directly; [integration points](../integrations/integration-points.md#llm-gateway) defines the egress boundary and marks retrieval/tool calling as future work.

## Add or migrate a feature

1. Decide scope: shared Hitachi feature, CD-SEM/HV-SEM-specific feature, or top-level product feature.
2. Create `routes.py` exporting globally unique `bp`, `data.py`, `contracts.py`, `providers/mock.py`, and tracked `providers/office_example.py`.
3. Keep route validation and HTTP behavior in `routes.py`; keep source selection in `data.py`; keep transport queries and normalization in providers. At the office, copy `office_example.py` to ignored `office.py` and implement only that local file.
4. Add the frontend composable and page/component consumers against `/api`, without environment branches.
5. Add provider contract tests and representative route tests. For office migration, run the same gate with the feature override set to `office`.
6. Update API contracts and migration notes, then follow [operations](../operations/runbook.md) and [testing guidance](../testing/guidance.md).

Blueprint registration is automatic. Verify application startup because discovery imports every route module. Prefer a clear `NotImplementedError` over an office adapter returning plausible empty data.
