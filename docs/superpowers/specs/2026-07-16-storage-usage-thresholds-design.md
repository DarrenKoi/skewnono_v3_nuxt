# Storage usage thresholds — Design

- Date: 2026-07-16
- Status: Approved (design)
- Area: `front-dev-home` storage page

## Problem

The storage page currently classifies usage below 60% as healthy, usage from
60% through 79% as warning, and usage of at least 80% as critical. The required
operational thresholds are now:

- Healthy: below 90%
- Warning: 90% through 97%
- Critical: 98% or above

The same classification must drive the usage colors, filter options, filter
results, and summary counts so the page cannot show conflicting states.

## Design

Add a small pure utility under `front-dev-home/app/utils/` that owns the storage
usage thresholds and maps a numeric percentage to `healthy`, `warning`, or
`critical`.

`StorageView.vue` will consume this classification in each existing behavior:

- Usage bar and percentage text colors
- Usage-filter labels and matching
- Healthy, warning, and critical summary counts

The filter labels will read:

- `위험 (98% 이상)`
- `주의 (90–97%)`
- `정상 (90% 미만)`

The existing `unavailable` classification and `정보 없음` filter remain
unchanged. Existing unrelated edits in `StorageView.vue`, including IP-copy
behavior, remain untouched.

## Testing

Add a Node test beside the utility covering the four important boundaries:

- 89% is healthy.
- 90% is warning.
- 97% is warning.
- 98% is critical.

Implementation follows red-green-refactor: add and run the boundary test before
adding the utility, then update the component to consume the passing utility.
Run the focused test, the frontend test suite, ESLint, Nuxt type checking, and
`git diff --check` before completion.

## Scope

- No backend response-shape or mock-data changes.
- No layout or styling-token changes.
- No recipe-count threshold changes.
- No changes to storage unavailable handling.
