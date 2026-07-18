---
type: Domain Guide
title: Product and Metrology Concepts
description: Canonical engineering summary of SKEWNONO metrology language, Device Statistics rules, Skewvoir review semantics, AFM analysis, and cross-cutting product surfaces.
resource: CONTEXT.md
tags: [domain, metrology, device-statistics, skewvoir, afm]
---

# Product and metrology concepts

`CONTEXT.md` is the repository's shared-language source; ADRs and implementation contracts refine it. This page selects the concepts that affect architecture and code. Consult `docs/project-overview.md` for the broader product narrative.

## Equipment and analysis scope

SKEWNONO v3 expands CD-SEM operations to a wider E-Beam platform including HV-SEM, with AFM already integrated and Thickness represented as an emerging route area. Analyses are generally closed within one fab: crossing R3 and M-fab boundaries is not considered a valid Device Statistics comparison.

A **lot** is both a device identifier and the primary ownership axis. Users recognize team ownership from `lot_cd`, so Device Statistics starts at lots rather than recipes. ADR `docs/adr/0001-lot-as-primary-axis.md` records this decision.

A **recipe** defines a measurement operation and pairs with an **oper ID**. Each recipe contains named **parameters** with measurement-point counts. Parameter type—WAFER, LEVEL, EDGE, EDGE_EX, or other—is derived from its name and drives governance rules.

## Device Statistics and measurement governance

[Device Statistics workflow](../workflows/key-workflows.md#device-statistics) helps operators identify oversized measurements and helps leaders compare lots on one shareable page. ADR `0002-shared-url-across-audiences.md` explains why both audiences share the same URL rather than being hidden behind role-specific tabs.

### Buckets and TAT

The page-wide bucket selects how recipe steps are interpreted for rule evaluation; it does not change the visible lot/recipe population. The modes are `all`, `only_normal`, `mother_normal`, and `only_sample`. **Mother** parameters drive Turn-Around Time, while **son** parameters are acquired within a mother measurement without separate TAT impact. `mother_normal` is therefore the default optimization view.

### Measurement rules

A measurement rule is a parameter-type point-count cap plus optional name overrides. Compliance means every parameter is at or below its cap; under-measurement is not a violation because the goal is suppressing measurement bloat. Raw parameter rows are the source of truth. Legacy `para_16/13/9/5` bins are derived summaries and cannot express rules such as `EDGE_EX=0`.

Recipe classification is Main, Sample, or additional measurement. R3 rule resolution uses recipe class, product family, phase or yield-check status, and memory class. M-fab rules use recipe class and memory class without the R3 development axes. Product family and development phase are orthogonal and are derived by the backend from source text.

A **lot health signal** rolls recipe violations into green/yellow/red using editable thresholds. It is a shared cross-team truth, not a personal override. The active UI can read seed rules and evaluate them client-side; persistence, history, and rollback remain incomplete.

This domain [depends on stable provider contracts](../architecture/overview.md#provider-seam-and-contracts) because office migration must preserve the parameter-level evidence required by the rule engine.

## Skewvoir review model

A **review candidate** is one MSR measurement execution. A questionable parameter, site, image, or equipment condition is **review evidence**, not a separate top-level candidate.

Evidence is grouped into:

- measurement results: parameter distributions and site patterns;
- equipment state: FDC and drift;
- execution/data quality: alignment, image failures, missing data, and measurement scores.

**Review priority** is not an average of every signal. Data quality first gates whether measurement evidence is trustworthy; the highest remaining severity then determines which MSR to inspect first.

An **official review assessment** uses a versioned, reproducible **reference cohort**. Compatibility requires the same fab, equipment type/model, exact recipe, parameter, and measurement/site layout; lot and individual tool may differ so those variations remain detectable. Too few compatible references means *unevaluated*, not normal.

A user-curated **comparison set** produces an exploratory assessment only. It may visualize differences but must not modify official status. The [Skewvoir workflow](../workflows/key-workflows.md#skewvoir-search-and-analysis) preserves focus, set, parameter, site, metric, and related analysis state in the URL so evidence can be shared and reproduced.

## AFM

The integrated AFM area organizes measurements by tool and file, then exposes point tables, summary scatter, wafer heatmaps, height histograms, profile images, and analysis artifacts. A cart drives multi-measurement “see together” analysis.

`front-dev-home/app/pages/afm/` and `back_dev_home/afm/` are the active application. `afm_data_platform/` is the standalone source system retained for migration semantics, dummy-data/cache utilities, and compatibility reference. Recent history moved heatmap, histogram, and table calculations into pure tested utilities before layering controls into Vue components.

## Chat and cross-cutting administration

The chat surface stores per-user threads and forwards conversation history to an OpenAI-compatible completion endpoint. It currently is ordinary conversational completion; repository plans for retrieval and tool calling are future design, not active runtime behavior.

Access control, activity analytics, API tokens, and admin logs are shared operational domains. Authentication [secures the runtime](../architecture/overview.md#identity-authorization-and-observability); token calls are visible in logs but excluded from human usage scoring. These workflows rely on provider-backed persistence and observability described in [integration points](../integrations/integration-points.md).

## Change guardrails

- Keep lot as the Device Statistics outer axis and fab as its closed scope.
- Do not collapse raw parameters back into point-count bins for rule evaluation.
- Keep official cohorts immutable from exploratory selection controls.
- Call insufficient evidence “unevaluated”; do not imply normality.
- Treat MSR as the review unit and lower-level signals as evidence.
- Preserve URL-state semantics for shared analytical artifacts.
- Verify changes against `CONTEXT.md`, relevant ADRs, API contracts, and [testing guidance](../testing/guidance.md).
