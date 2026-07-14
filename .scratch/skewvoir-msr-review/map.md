# Trustworthy MSR review detection

Label: `wayfinder:map`

## Destination

Produce an implementation-ready specification for a contextual MSR review system across the CD-SEM and HV-SEM Skewvoir search and analysis flow. The specification must define trustworthy reference cohorts, review evidence, user-visible states, storage/API boundaries, validation, and human review outcomes without claiming that a flagged MSR is defective.

## Notes

- Domain language lives in [CONTEXT.md](../../CONTEXT.md). Sessions should use the `wayfinder`, `domain-modeling`, and `grilling` skills; external method research uses the `research` skill.
- One MSR is the top-level Review Candidate. Parameter, site, tool-condition, and execution/data-quality findings are supporting Review Evidence.
- Official Review Assessments use an automatic, reproducible Reference Cohort. User-authored Comparison Sets and threshold changes are exploratory only.
- The initial strict cohort compatibility setting matches fab, tool type/model, exact recipe, parameter, and measurement/site layout. Lot and individual equipment ID may differ.
- Official user-facing states are Not evaluated, No review flag, Watch, and Needs review. Insufficient evidence is not No review flag.
- Evidence families are measurement outcome, tool condition, and execution/data quality. Quality gates run first; otherwise the highest trustworthy evidence determines priority. Evidence is never averaged into an opaque health score.
- Search uses OpenSearch metadata plus precomputed review summaries. After row click or multi-selection, Flask resolves the MinIO path, reads the object, and returns normalized versioned JSON through `/api/msr-file` or `/api/msr-files`; the browser never accesses MinIO directly.
- Human Review Outcomes are retained with user, time, comment, detector version, and evidence snapshot. Online retraining is not part of the initial system.
- Release requires one offline acceptance evaluation against engineer-reviewed historical MSRs. A mandatory shadow phase is not required.
- Current source anchors: [analysis composition](../../front-dev-home/app/composables/useSkewvoirAnalysis.ts), [anomaly utilities](../../front-dev-home/app/utils/anomaly/), [search results](../../front-dev-home/app/components/ebeam/skewvoir/search/ResultTable.vue), [measurement search API](../../back_dev_home/meas_hist/routes.py), and [MSR detail API](../../back_dev_home/msr_file/routes.py).
- Phase 1 remains mock-backed. Office-specific OpenSearch mappings, MinIO formats, and operational characteristics must be inventoried before the final contract is locked.

## Decisions so far

- [Choose trustworthy evidence-scoring methods](issues/01-choose-trustworthy-evidence-scoring-methods.md) — Use quality gates, robust per-feature median/MAD peer evidence, and separate frozen-baseline EWMA; keep percentage limits domain-owned and defer multivariate official scoring.

## Not yet specified

- Backfill, re-evaluation, and stale-assessment operations cannot be specified until the office inventory and assessment persistence decisions expose data volume, ingestion timing, and consistency constraints.
- Whether a later detector generation should introduce multivariate or learned methods remains fog until interpretable-method research and the initial offline acceptance results establish the remaining failure modes.

## Out of scope

- Implementing the detector, ingestion worker, API, or UI while this map is being resolved.
- Declaring an MSR or its data defective without human review.
- Direct browser access to MinIO paths, objects, or credentials.
- Silent relaxation of cohort compatibility for an official assessment.
- Cross-fab or cross-model official comparison under the initial strict setting.
- Automatic remediation, process control, or equipment intervention.
- Automatic online retraining from user feedback.
- A mandatory shadow/preview rollout period.
