---
type: Domain Guide
title: Product and Metrology Concepts
description: Canonical engineering summary of SKEWNONO metrology language, FAB and recipe identity, equipment analytics, Device Statistics rules, Skewvoir review semantics, Mag/Pixel setup, AFM, and chat.
resource: CONTEXT.md
tags: [domain, metrology, device-statistics, skewvoir, afm]
---

# Product and metrology concepts

`CONTEXT.md` is the repository's shared-language source; ADRs and implementation contracts refine it. This page selects the concepts that affect architecture and code. Consult `docs/project-overview.md` for the broader product narrative.

## Equipment and analysis scope

SKEWNONO v3 expands CD-SEM operations to a wider E-Beam platform including HV-SEM, with AFM code integrated but currently hidden from users and Thickness represented as an emerging route area. Analyses are generally closed within one fab: crossing R3 and M-fab boundaries is not considered a valid Device Statistics comparison.

A **lot** is both a device identifier and the primary ownership axis. Users recognize team ownership from `lot_cd`, so Device Statistics starts at lots rather than recipes. ADR `docs/adr/0001-lot-as-primary-axis.md` records this decision.

A **recipe** defines a measurement operation and pairs with an **oper ID**. Each recipe contains named **parameters** with measurement-point counts. Parameter type—WAFER, LEVEL, EDGE, EDGE_EX, or other—is derived from its name and drives governance rules.

## Device Statistics and measurement governance

[Device Statistics workflow](../workflows/key-workflows.md#device-statistics) helps operators identify oversized measurements and helps leaders compare lots on one shareable page. ADR `0002-shared-url-across-audiences.md` explains why both audiences share the same URL rather than being hidden behind role-specific tabs.

### Buckets and TAT

The page-wide bucket selects how recipe steps are interpreted for rule evaluation; it does not change the visible lot/recipe population. The modes are `all`, `only_normal`, `mother_normal`, and `only_sample`. **Mother** parameters drive Turn-Around Time, while **son** parameters are acquired within a mother measurement without separate TAT impact. `mother_normal` is therefore the default optimization view.

### Measurement rules

A measurement rule is a parameter-type point-count cap plus optional name overrides. Compliance means every parameter is at or below its cap; under-measurement is not a violation because the goal is suppressing measurement bloat. Raw parameter rows are the source of truth. Legacy `para_16/13/9/5` bins are derived summaries and cannot express rules such as `EDGE_EX=0`.

Recipe classification is Main, Sample, or additional measurement. The rules API and every selector call this feature's factory axis `fac_id`, intentionally differing from the repository-wide `fab_name` convention. The current seed publishes rules only for R3: resolution uses recipe class, product family, phase or yield-check status, and memory class. Product family and development phase are orthogonal and are derived by the backend from source text.

A **lot health signal** rolls recipe violations into green/yellow/red using editable thresholds. It is a shared cross-team truth, not a personal override. The active UI can read seed rules and evaluate them client-side; persistence, history, and rollback remain incomplete.

This domain [depends on stable provider contracts](../architecture/overview.md#provider-seam-and-contracts) because office migration must preserve the parameter-level evidence required by the rule engine.

## Equipment identity and tool families

The SEM-list is the roster of record. `eqp_id` is a lookup key, not a tool-family classifier: `_tool_specs.py` classifies model-code series prefixes into four canonical families—`cdsem`/`cd-sem`, `hvsem`/`hv-sem`, `veritysem`/`veritysem`, and `provision`/`provision`. The canonical VeritySEM product and route spelling is `veritysem`; `verity_sem` remains only as a historical activity label. CD/HV-only routes reject AMAT slugs rather than fabricating rows.

This identity model [drives the Tool Roster workflow](../workflows/key-workflows.md#tool-roster-and-firewall-requests) and [supports storage's SEM-list join](../integrations/integration-points.md#sem-list-redis-adapter).

## Equipment analytics

Recipe TAT and fail issue compare equipment only after accounting for each tool's recipe mix. Recipe TAT's **TAT index** is actual total TAT divided by expected TAT for that tool's recipe mix; too few executions produce `null`, meaning unevaluated. **Measurement occupancy** is time occupied by measurements, not MES uptime. Fail issue independently computes observed/expected **Align** and **Meas** indices; one execution may contribute to both. Each fail index is all-or-nothing with a Byar 95% interval, and insufficient expected failures make the index and interval `null` rather than healthy.

Equipment badges combine absolute and peer-relative evidence. Fail badges additionally require the confidence interval to lie wholly above or below expected. When returned equipment spans multiple FABs, peer badges are suppressed because the mixed peer group is confounded. These concepts [surface through the equipment analytics workflow](../workflows/key-workflows.md#recipe-tat-and-fail-issue-equipment-analytics); exact fields and thresholds live in `docs/api-contracts/recipe-tat.yaml`, `docs/api-contracts/fail-issue.yaml`, and the feature `MIGRATION.md` files.

## Skewvoir review model

A **review candidate** is one MSR measurement execution. A questionable parameter, site, image, or equipment condition is **review evidence**, not a separate top-level candidate.

Evidence is grouped into:

- measurement results: parameter distributions and site patterns;
- equipment state: FDC and drift;
- execution/data quality: alignment, image failures, missing data, and measurement scores.

**Review priority** is not an average of every signal. Data quality first gates whether measurement evidence is trustworthy; the highest remaining severity then determines which MSR to inspect first.

An **official review assessment** uses a versioned, reproducible **reference cohort**. Compatibility requires the same fab, equipment type/model, exact recipe, parameter, and measurement/site layout; lot and individual tool may differ so those variations remain detectable. Too few compatible references means *unevaluated*, not normal.

A user-curated **comparison set** produces an exploratory assessment only. It may visualize differences but must not modify official status. The [Skewvoir workflow](../workflows/key-workflows.md#skewvoir-search-and-analysis) preserves focus, set, parameter, site, metric, and related analysis state in the URL so evidence can be shared and reproduced.

A **focused sequence/site** is the current inspection cursor; **selected measurement points** are a separate comparison set keyed by `(parameter, sequence)`. Selection order assigns stable identity colors across the table, wafer map, radius plot, and distribution. Those colors identify the same point across views and must not be confused with severity or heat-scale colors. Filtering may hide selected points but does not discard them.

## CD-SEM Mag/Pixel setup

The [Mag/Pixel workflow](../workflows/key-workflows.md#cd-sem-magpixel-setup) balances two opposing constraints. The field of view must contain the requested pattern span plus a per-edge margin, which places an upper bound on magnification; the CD must occupy at least the chosen pixels-per-CD threshold, which places a lower bound on pixel density. The recommendation therefore chooses the highest available discrete magnification that still fits the pattern and then the smallest pixel setting that meets the threshold, because scan cost grows with the square of the pixel dimension.

FOV is width-based: `FOV_nm = 135,000 × 1,000 / magnification`, and `nm/px = FOV_nm / horizontal_pixels`. For non-square acquisition settings, the X component is authoritative. Missing pitch is disclosed as an assumed `CD × 2`; pitch must be strictly greater than CD so a line/space pattern retains nonzero space. The GT 600K–1M magnification tail is also explicitly assumed, and the default minimum px/CD remains provisional rather than an approved metrology standard. The same calculation [calibrates Skewvoir gallery metadata](../workflows/key-workflows.md#skewvoir-search-and-analysis), so setup guidance and acquired-image interpretation must evolve together (`app/utils/magPixel.ts`).

## AFM

The integrated AFM area organizes measurements by tool and file, then exposes point tables, summary scatter, wafer heatmaps, height histograms, profile images, and analysis artifacts. A cart drives multi-measurement “see together” analysis.

`front-dev-home/app/pages/afm/` and `back_dev_home/afm/` contain the integrated implementation, but `useAfmAvailability.ts` currently disables product exposure and global middleware redirects `/afm/*`. The former standalone `afm_data_platform/` was removed after migration; `docs/afm-migration-plan.md`, `docs/afm/`, and Git history preserve its design context. Recent history moved heatmap, histogram, and table calculations into pure tested utilities before layering controls into Vue components. The workflow [still depends on an unconnected office source](../integrations/integration-points.md#afm-office-source), so integrated code does not imply live office AFM data.

## Chat and cross-cutting administration

The chat surface stores per-user threads and supports either direct OpenAI-compatible completion or a bounded retrieval agent. Agent mode exposes only configured, available read-only manual, meeting, email, and report tools; scope classification may refuse unsupported requests or send only the supported portion. Synthetic retrieval is implemented, but office knowledge retrieval, authoritative group/FAB scope resolution, and office thread storage remain separate activation work. The [chat workflow](../workflows/key-workflows.md#chat) and [LLM integration](../integrations/integration-points.md#llm-gateway-and-retrieval-runtime) define those boundaries.

Access control, activity analytics, API tokens, and admin logs are shared operational domains. Authentication [secures the runtime](../architecture/overview.md#identity-authorization-and-observability); token calls are visible in logs but excluded from human usage scoring. These workflows rely on provider-backed persistence and observability described in [integration points](../integrations/integration-points.md).

## Change guardrails

- Keep lot as the Device Statistics outer axis and fab as its closed scope.
- Do not collapse raw parameters back into point-count bins for rule evaluation.
- Keep official cohorts immutable from exploratory selection controls.
- Call insufficient evidence “unevaluated”; do not imply normality.
- Treat MSR as the review unit and lower-level signals as evidence.
- Preserve URL-state semantics for shared analytical artifacts.
- Verify changes against `CONTEXT.md`, relevant ADRs, API contracts, and [testing guidance](../testing/guidance.md).
 [secures the runtime](../architecture/overview.md#identity-authorization-and-observability); token calls are visible in logs but excluded from human usage scoring. These workflows rely on provider-backed persistence and observability described in [integration points](../integrations/integration-points.md).

## Change guardrails

- Keep lot as the Device Statistics outer axis and fab as its closed scope.
- Do not collapse raw parameters back into point-count bins for rule evaluation.
- Keep official cohorts immutable from exploratory selection controls.
- Call insufficient evidence “unevaluated”; do not imply normality.
- Treat MSR as the review unit and lower-level signals as evidence.
- Preserve URL-state semantics for shared analytical artifacts.
- Verify changes against `CONTEXT.md`, relevant ADRs, API contracts, and [testing guidance](../testing/guidance.md).
