# Trustworthy MSR Review Detection

Status: `ready-for-agent`

Source map: [Trustworthy MSR review detection](map.md)

## Problem Statement

Skewvoir 사용자는 측정 이력을 검색한 뒤 여러 MSR을 분석하지만, 현재의 이상치 표시는 사용자가 직접 고른 Comparison Set 안에서만 계산됩니다. 사용자가 MSR을 추가하거나 제거하면 같은 MSR의 판정도 달라질 수 있으며, 서로 다른 fab·장비 모델·recipe·parameter·측정 배치를 섞으면 통계적으로는 큰 차이가 보여도 업무적으로는 비교할 수 없는 값일 수 있습니다.

현재 표시는 `normal / watch / abnormal / insufficient` 용어와 사용자가 직접 바꾸는 임계치를 사용합니다. 이 방식은 탐색에는 유용하지만, 여러 사용자가 공유하는 공식 검토 우선순위로 쓰기에는 재현성이 부족합니다. 또한 `abnormal`은 탐지기가 데이터 불량을 확정한 것처럼 읽힐 수 있고, `insufficient`가 정상처럼 묻힐 위험이 있습니다.

MSR에는 parameter·site 측정값뿐 아니라 고정/동적 FDC, 정렬, 이미지 실패, 측정 점수 등 장비 상태와 실행 품질 정보가 함께 있습니다. 그러나 이 근거가 하나의 MSR 단위 검토 흐름으로 통합되어 있지 않으므로, 사용자는 어떤 측정을 먼저 확인해야 하는지, 왜 확인해야 하는지, 확인 후 무엇을 결론 냈는지를 일관되게 다루기 어렵습니다.

Office 환경에서는 검색용 문서가 OpenSearch에 있고 전체 MSR 객체는 MinIO에 저장되며, OpenSearch 문서가 MinIO 경로를 가집니다. 검색 결과마다 MinIO 객체를 즉시 읽으면 N+1 조회가 발생합니다. 반대로 MinIO를 열기 전까지 아무 상태도 보여주지 않으면 사용자는 문제 후보를 찾기 위해 MSR을 하나씩 열어야 합니다.

## Solution

Skewvoir에 MSR 중심의 contextual review system을 도입합니다. 한 MSR을 최상위 **Review Candidate**로 정의하고, parameter·site·장비 상태·실행/데이터 품질의 차이는 그 MSR에 연결된 **Review Evidence**로 제공합니다. 표시는 데이터가 불량하다는 확정 판정이 아니라 사용자가 확인할 우선순위입니다.

공식 **Official Review Assessment**는 시스템이 자동으로 구성한 재현 가능한 **Reference Cohort**를 사용합니다. 초기 strict compatibility는 fab, tool type과 equipment model, exact recipe, parameter, measurement/site-layout signature를 일치시킵니다. Lot과 개별 equipment ID는 달라도 되므로 lot별 또는 장비별 차이를 발견할 수 있습니다. 호환 가능한 MSR이 부족하면 조건을 자동 완화하지 않고 `Not evaluated`를 반환합니다.

검색 경로와 상세 경로를 분리합니다. OpenSearch 검색 문서는 precomputed review summary를 포함하므로 검색 결과에서 `No review flag / Watch / Needs review / Not evaluated`를 바로 표시하고 필터·정렬할 수 있습니다. 사용자가 한 행을 열거나 여러 행을 선택하면 Flask backend가 OpenSearch에서 MinIO 경로를 확인하고 MinIO 객체를 읽은 뒤, 검증·정규화된 versioned JSON을 기존 single/batch MSR API를 통해 frontend에 반환합니다. Browser는 MinIO 경로·객체·credential에 직접 접근하지 않습니다.

Review Evidence는 `measurement outcome`, `tool condition`, `execution/data quality` 세 family로 구분합니다. 실행/데이터 품질이 측정 결론을 신뢰할 수 있는지 먼저 gate하고, gate를 통과한 evidence 중 가장 높은 신뢰 가능한 severity가 Review Priority를 결정합니다. 서로 다른 근거를 하나의 불투명한 health score로 평균내지 않으며, 각 reason과 평가 가능 여부를 보존합니다.

공식 detector configuration과 threshold는 server-side에서 공유·version 관리합니다. 사용자는 Comparison Set이나 local threshold로 **Exploratory Assessment**를 수행할 수 있지만, 이는 공식 상태를 변경하지 않습니다. 공식 방법과 threshold는 offline acceptance dataset으로 검증된 configuration version이 게시된 뒤 활성화하며, 게시 전이거나 configuration이 stale하면 `Not evaluated`로 표시합니다.

초기 공식 method set은 deterministic execution/data-quality gate, feature별 leave-candidate-out median/MAD peer evidence, 그리고 안정된 time stream에 대한 별도 frozen-baseline EWMA입니다. Percentage limit는 domain owner가 정한 feature-specific engineering review limit일 때만 공식 근거로 사용합니다. Multivariate distance는 초기 공식 평가에서 제외합니다.

사용자는 분석 후 **Review Outcome**을 남길 수 있습니다. 결과는 measurement/process concern, tool-condition concern, execution/data-quality problem, expected variation/false alert, inconclusive로 구분하며 user, timestamp, comment, detector/configuration version, evidence snapshot을 함께 보존합니다. 이 feedback은 offline validation과 이후 threshold 조정에 사용하지만 초기 범위에서 automatic online retraining은 하지 않습니다.

## User Stories

1. As a metrology engineer, I want to see Review Priority in measurement search results, so that I can identify which MSRs deserve attention before opening them.
2. As a metrology engineer, I want to filter search results by `Needs review`, `Watch`, `No review flag`, and `Not evaluated`, so that I can focus on the appropriate review queue.
3. As a metrology engineer, I want to sort search results by Review Priority and capture time, so that urgent and recent candidates appear first.
4. As a metrology engineer, I want each flagged search row to show a concise top reason, so that I understand why it was prioritized.
5. As a metrology engineer, I want `Not evaluated` to remain visibly different from `No review flag`, so that missing evidence is never mistaken for a clean result.
6. As a metrology engineer, I want stale assessments to be identified, so that I do not rely on a result produced from an outdated object or configuration.
7. As a metrology engineer, I want search to remain lightweight without loading every MinIO object, so that normal search latency does not grow with result count.
8. As a metrology engineer, I want to open one search row by its stable MSR identity, so that I can inspect the complete measurement and tool-condition evidence.
9. As a metrology engineer, I want to select MSRs across multiple search result pages or searches, so that I can build a Comparison Set without losing earlier selections.
10. As a metrology engineer, I want one batch action to open all selected MSRs, so that I do not trigger one browser request per measurement.
11. As a metrology engineer, I want one missing or corrupt MinIO object to appear as an item-level error, so that the rest of a multi-selection still loads.
12. As a metrology engineer, I want batch results to preserve the authored MSR order, so that the analysis matches my selection.
13. As a metrology engineer, I want a persistent Review Summary in the analysis workspace, so that the current MSR's official status remains visible across analysis views.
14. As a metrology engineer, I want the Review Summary to show all three evidence families separately, so that a tool concern is not confused with a measurement concern.
15. As a metrology engineer, I want measurement-outcome evidence to identify the affected parameter and metric, so that I can open the relevant chart directly.
16. As a metrology engineer, I want site-pattern evidence to identify affected sites or spatial signatures, so that I can verify the pattern on wafer and position views.
17. As a metrology engineer, I want tool-condition evidence to identify the responsible fixed or sequence-level FDC signals, so that I can inspect equipment behavior.
18. As a metrology engineer, I want execution/data-quality evidence to identify alignment, image-failure, missing-value, or measurement-score problems, so that I can distinguish invalid input from a process shift.
19. As a metrology engineer, I want unsupported measurement conclusions to be suppressed when the quality gate fails, so that unreliable values are not presented as process evidence.
20. As a metrology engineer, I want every evidence reason to include observed value, reference value or band, method, and direction of deviation when applicable, so that the flag is explainable.
21. As a metrology engineer, I want to see the Reference Cohort compatibility criteria and effective peer count, so that I can judge whether the comparison is credible.
22. As a metrology engineer, I want cohort relaxation to require an explicit exploratory action, so that the official assessment never silently compares incompatible MSRs.
23. As a metrology engineer, I want lot and individual equipment ID to remain contrast dimensions rather than compatibility keys, so that lot-specific and tool-specific differences can surface.
24. As a metrology engineer, I want manually selecting a Comparison Set to leave the Official Review Assessment unchanged, so that the official status is reproducible.
25. As a metrology engineer, I want locally changing exploratory thresholds to leave the Official Review Assessment unchanged, so that colleagues see the same official result.
26. As a metrology engineer, I want official and exploratory states to be labeled explicitly, so that screenshots and shared links cannot be misread.
27. As a metrology engineer, I want the analysis URL to retain the selected MSR, parameter, view, and Comparison Set, so that another user can reopen the same evidence context.
28. As a metrology engineer, I want to classify my Review Outcome as a measurement/process concern, so that validated process evidence is retained.
29. As a metrology engineer, I want to classify my Review Outcome as a tool-condition concern, so that validated equipment evidence is retained.
30. As a metrology engineer, I want to classify my Review Outcome as an execution/data-quality problem, so that invalid measurements are separated from process concerns.
31. As a metrology engineer, I want to mark expected variation or a false alert, so that future offline calibration can measure false-positive burden.
32. As a metrology engineer, I want to mark a review as inconclusive, so that uncertainty is recorded instead of forcing an unsupported conclusion.
33. As a reviewer, I want to add a comment to a Review Outcome, so that the conclusion retains necessary engineering context.
34. As a reviewer, I want the outcome to retain the evidence snapshot and detector/configuration version, so that later re-evaluation does not rewrite what I originally reviewed.
35. As a reviewer, I want the submitter and review time to be auditable, so that conclusions have accountable provenance.
36. As a detector configuration owner, I want official settings to be shared and versioned, so that every user receives the same assessment for the same MSR and source version.
37. As a detector configuration owner, I want a previous configuration to remain identifiable, so that results can be reproduced and rollback can be supported.
38. As a detector configuration owner, I want a configuration without sufficient offline evidence to remain unpublished, so that unvalidated thresholds cannot create official flags.
39. As a product owner, I want the release acceptance report to include cohort coverage, false-alert rate, missed known concerns, and alerts per day, so that operational usefulness is measured before release.
40. As a product owner, I want release evaluation sliced by evidence family and key cohort dimensions, so that an acceptable aggregate does not hide a failing subgroup.
41. As a backend developer, I want the frontend contract to be independent of the MinIO object format, so that storage-format changes do not require feature-code changes.
42. As a backend developer, I want OpenSearch to provide only searchable metadata and review summaries, so that search does not depend on raw-object retrieval.
43. As a backend developer, I want MinIO objects to be parsed, validated, and normalized behind Flask, so that untrusted or incompatible payloads do not leak into the browser.
44. As a backend developer, I want single and batch responses to use the same normalized MSR representation, so that frontend behavior remains consistent.
45. As a backend developer, I want partial batch failures represented per MSR, so that one failure does not erase successful results.
46. As an office adapter developer, I want Phase 1 mock and Phase 2/3 providers to preserve the same response shapes, so that frontend feature code does not branch by environment.
47. As an office operator, I want review summaries to identify source-object and assessment freshness, so that ingestion delays or reprocessing gaps are visible.
48. As a user, I want existing search errors, retention limits, and capped-result warnings to remain visible, so that review status does not hide basic data-access limitations.
49. As a user, I want the same workflow for CD-SEM and HV-SEM, so that Review Priority has one meaning across both Skewvoir routes.
50. As a user, I want the system to say `Needs review` rather than declare data abnormal, so that human judgment remains the final authority.

## Implementation Decisions

1. **Review Candidate boundary:** One MSR is the only top-level Review Candidate. Parameter, site, FDC, alignment, image, and quality findings are Review Evidence attached to that MSR; they do not create independent top-level inbox items.

2. **Official versus exploratory authority:** Official Review Assessments are server-produced, reproducible, and shared. Comparison Sets and user-local thresholds produce Exploratory Assessments only. The UI must never allow exploratory inputs to overwrite or visually impersonate the official result.

3. **Reference Cohort compatibility:** The initial strict compatibility key includes fab, tool type, equipment model, exact recipe, parameter, and measurement/site-layout signature. Lot and individual equipment ID are excluded from the key so they remain observable contrast dimensions. Compatibility is not silently relaxed.

4. **Sufficiency behavior:** Method-specific reference window, minimum effective sample, and freshness requirements belong to versioned detector configuration. When any required criterion is missing, the official evaluation state is `Not evaluated`; it does not fall back to `No review flag`, older incompatible data, or a user-authored set.

5. **User-visible state model:** Evaluation status and Review Priority are separate axes. An unevaluated assessment has `Not evaluated` and no priority. An evaluated assessment has one of `No review flag`, `Watch`, or `Needs review`. Existing internal anomaly types may be migrated, but user-facing language must use the new vocabulary.

6. **Evidence families:** The normalized assessment retains measurement outcome, tool condition, and execution/data quality as separate families. Evidence records include stable evidence identity, family, metric or signal, evaluation status, severity, observed value when available, reference context, reason, and affected parameter/site/FDC identity.

7. **Quality gate and roll-up:** Execution/data-quality rules run before measurement interpretation. A failed quality gate creates review evidence and suppresses conclusions it makes unreliable. Otherwise, the highest-severity trustworthy evidence sets MSR Review Priority. Evidence is not averaged into a single opaque health scalar, and insufficient evidence remains visible even when another family is evaluated.

8. **Initial scoring method set:** Deterministic execution/data-quality gates run first. Each predeclared scalar measurement, site-summary, and tool-condition feature uses leave-candidate-out median/MAD peer evidence while retaining signed raw and percentage deltas for explanation. Percentage thresholds run separately only as feature-specific engineering review limits approved by a domain owner. Stable time streams may use one frozen/versioned EWMA for sustained drift. The initial readiness candidates are at least 20 finite compatible peers for median/MAD and at least 25 accepted ordered baseline observations for EWMA; the offline acceptance gate must sweep and confirm these product settings. Zero MAD without a domain resolution rule, invalid near-zero percentage reference, inadequate peers, or inadequate temporal baseline produces `Not evaluated`. Fixed mean/sigma scoring remains exploratory, and multivariate official scoring is deferred.

9. **Precomputation:** Official assessments are computed server-side after the measurement document and referenced MinIO object are available. Search requests do not calculate assessments from full raw objects. Re-evaluation writes a new versioned assessment summary rather than changing the meaning of an old evidence snapshot.

10. **OpenSearch search contract:** Each searchable measurement row may include a nullable `review_summary` containing evaluation status, priority, top reasons, evidence-family counts, detector version, configuration version, cohort identity/count, evaluated time, source-object version, and stale indicator. Existing search, retention, pagination, and capped-result fields remain stable. Missing summaries render as `Not evaluated`, not as an error or clean result.

11. **MinIO access boundary:** The browser sends stable MSR identities only. Flask resolves the authorized OpenSearch document and MinIO path, retrieves the object, validates its supported format/version, and returns normalized JSON. MinIO path, raw pickle/object bytes, and credentials are not frontend contract fields.

12. **Normalized MSR contract:** The single-MSR response is versioned and includes measurement identity/metadata, parameter summaries, normalized site rows, fixed and sequence-level FDC, execution/data-quality fields, source-object version/freshness, and detailed Official Review Assessment. Storage-specific fields remain behind the provider boundary.

13. **Batch MSR contract:** Multi-selection uses one backend batch request. The backend bulk-resolves OpenSearch documents, retrieves MinIO objects with bounded concurrency, preserves request order, and returns an item result for every requested MSR. Each item is either a normalized MSR payload or a structured not-found, unauthorized, missing-object, unsupported-format, corrupt-object, or transient-retrieval error. One item failure does not fail successful items.

14. **Frontend search behavior:** Search results gain Review Priority, top-reason, filter, and sort behavior without automatically loading MinIO objects. Existing explicit search, filter, selection persistence, retention warnings, pagination, and error-with-stale-results behaviors remain intact.

15. **Frontend analysis behavior:** The analysis workspace shows a persistent official Review Summary and evidence-family status. Evidence links or focuses the relevant parameter, site/spatial view, FDC view, or quality detail. Single row selection opens one MSR; multi-selection opens the authored Comparison Set through the batch contract. Official and exploratory legends remain visually distinct.

16. **Review Outcome contract:** A Review Outcome records category, reviewer identity, review time, optional comment, MSR identity, assessment/detector/configuration versions, and immutable evidence snapshot reference. The initial categories are measurement/process concern, tool-condition concern, execution/data-quality problem, expected variation/false alert, and inconclusive.

17. **Configuration governance:** Official configuration is shared, server-side, versioned, auditable, and rollback-capable. User-local controls are explicitly exploratory. Exact ownership and approval integration may reuse the repository's authenticated-user and audit conventions, but no personal official override is allowed.

18. **Cross-phase architecture:** Routes and frontend contracts remain identical across Phase 1, office-local, and production. Phase 1 supplies deterministic mock OpenSearch summaries and MinIO-normalized payloads. Office environments replace provider/data-access implementations, not route behavior or feature code.

19. **Failure and freshness semantics:** Search-summary absence, stale assessment, unsupported source version, insufficient cohort, MinIO retrieval failure, and detector failure are distinct states with distinct reasons. Previously rendered search results or successfully loaded batch items remain available when a refresh or sibling item fails.

20. **Superseded pilot assumptions:** The existing client-only anomaly pilot remains useful prior art for verdict composition, reasons, badges, and pure-function testing. Its manually selected peer set, local user thresholds, `normal/abnormal` language, and frontend-only authority do not define Official Review Assessment behavior under this specification.

## Testing Decisions

1. Tests assert externally visible contracts and decisions rather than private helper structure. The highest automated seam is the Flask API contract: search rows expose lightweight review summaries, while single/batch MSR APIs expose normalized detail and structured failures.

2. Search route contract tests cover both tool types, review-summary state vocabulary, missing/stale summaries, filters and sorting by priority, retention-window behavior, capped results, and preservation of existing search fields. The current home-safe Flask search tests are the prior-art pattern.

3. Single-MSR route contract tests cover successful OpenSearch path resolution, supported MinIO object normalization, no exposure of MinIO path or credentials, missing measurement document, unauthorized document, missing object, unsupported format/version, corrupt payload, and transient storage failure.

4. Batch route contract tests cover request-order preservation, bounded request limits, mixed success/failure results, duplicate MSR handling, one backend request from the frontend, and the rule that one item failure does not fail the batch.

5. Provider contract fixtures run against deterministic Phase 1 objects and office-local adapters. Office tests verify actual OpenSearch mappings, path resolution, MinIO object parsing, representative object size, and live single/batch retrieval without running in the home test suite. The existing split between home-safe and office-local measurement-search tests is prior art.

6. Pure detector tests cover cohort-key construction, strict compatibility, no silent relaxation, effective sample counting after invalid values are removed, `Not evaluated` behavior, quality-gate suppression, worst-trustworthy-evidence roll-up, reason payloads, and deterministic detector/configuration versioning.

7. Median/MAD and EWMA tests include adversarial fixtures for masking, multiple co-directional extremes, zero MAD, near-zero percentage centers, non-finite values, small samples, skewed or non-normal data, changed measurement layouts, frozen-baseline behavior, maintenance/regime boundaries, and sustained versus isolated shifts. Existing anomaly utility tests provide the pure `node:test` pattern.

8. Review-summary projection tests prove that a detailed assessment and its OpenSearch summary agree on status, priority, top reasons, version, cohort count, and stale state.

9. Frontend pure tests cover mapping API state to user-facing vocabulary, priority sort/filter semantics, persistence of multi-search selection by MSR, official versus exploratory separation, and partial batch-result merging. Existing measurement-selection and anomaly utility tests are prior art.

10. Browser verification covers search discovery, priority filtering/sorting, row click, multi-selection, loading and partial failure, persistent analysis summary, evidence navigation, Review Outcome entry, URL sharing, and explicit official/exploratory labels in light and dark modes. Because the repository has no dedicated E2E runner, these remain proportionate manual/in-app browser checks unless a runner is introduced separately.

11. The offline acceptance gate uses an engineer-reviewed historical dataset and leakage-safe replay. It reports Reference Cohort coverage, false-alert rate, missed known concerns, alerts per day, and slices by evidence family and important cohort dimensions. Exact pass thresholds are recorded in the configuration release artifact rather than hard-coded in tests.

12. Release verification includes frontend lint and typecheck, the complete frontend pure-test suite, backend home contract tests, office-local integration tests where infrastructure is available, Markdown lint for documentation changes, and whitespace validation.

## Out of Scope

- Declaring an MSR, parameter, or site defective without human review.
- Direct browser access to MinIO paths, objects, credentials, or raw object formats.
- Silent relaxation across fab, tool model, recipe, parameter, or measurement/site-layout compatibility for an Official Review Assessment.
- Cross-fab or cross-model official comparison in the initial strict configuration.
- Automatic remediation, process control, equipment intervention, or recipe modification.
- Automatic online learning or retraining from Review Outcomes.
- A mandatory shadow/preview rollout period; the offline acceptance gate is required instead.
- A learned or multivariate detector that cannot produce stable, engineer-readable evidence reasons.
- Replacing the existing search/analysis route split, URL-pinned selection, or environment swap architecture.
- Turning Review Outcomes into a general incident-management, assignment, escalation, or notification system.
- Loading every MinIO object during search merely to calculate or display Review Priority.

## Further Notes

- Primary-source [method research](../../docs/issues/skewvoir/msr-review-detection-research.md) recommends deterministic quality gates, leave-candidate-out median/MAD peer evidence, feature-specific domain limits, and a separate frozen-baseline EWMA. The current client-side leave-one-out mean/range and standard-deviation implementation remains useful exploratory prior art but is not promoted to official authority. The first official configuration still requires the offline acceptance artifact.
- Exact office OpenSearch mappings, MinIO object formats/sizes, ingestion ordering, retention, and access behavior remain environment facts to inventory. Those facts affect provider implementation and operational limits but must not change the normalized frontend contract.
- Backfill, re-evaluation scheduling, and stale-assessment operational policy should be finalized after office volume and ingestion timing are known. Until a fresh assessment exists, the UI must remain honest with `Not evaluated` or stale state.
- Existing anomaly badges, legends, verdict composition, search selection behavior, batch endpoint, and URL-driven analysis workspace should be reused where they satisfy this specification. Their current vocabulary or authority may be migrated without discarding the proven rendering and pure-test seams.
- A mandatory shadow rollout was explicitly rejected. Release confidence therefore depends on a credible engineer-reviewed offline dataset and documented acceptance results.
