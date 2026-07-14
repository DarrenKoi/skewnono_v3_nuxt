# Choose trustworthy evidence-scoring methods

Parent: [Trustworthy MSR review detection](../map.md)
Type: research
Status: resolved
Blocked by: none

## Question

Which robust, explainable detection and validation methods are best suited to strict contextual MSR cohorts and the three evidence families, especially when cohorts may be small or non-normal? Compare the current leave-one-out mean with percentage and standard-deviation bands against primary-source-supported alternatives such as robust location/scale statistics, statistical process-control rules, temporal drift methods, and appropriately constrained multivariate methods. State minimum-data assumptions, failure modes, explanation requirements, and a recommended initial method set for this system.

## Answer

Use deterministic execution/data-quality gates first, then leave-candidate-out median/MAD evidence for each predeclared scalar feature, preserving signed raw and percentage differences for explanation. Percentage limits remain explicit domain engineering limits, not statistical confidence. Add a separate frozen, versioned EWMA for valid temporal streams; enable additional run rules or CUSUM only if offline acceptance shows incremental value. Defer multivariate official scoring until office data demonstrates adequate `n` relative to `p`, stable robust covariance, and a reconstructable explanation. Start by testing peer `n >= 20` and temporal baseline `n >= 25` as conservative product gates; when a gate fails, return `Not evaluated` rather than relaxing the cohort. Full comparison, assumptions, failure modes, and citations: [Trustworthy Evidence-Scoring Methods for MSR Review](../../../docs/issues/skewvoir/msr-review-detection-research.md).
