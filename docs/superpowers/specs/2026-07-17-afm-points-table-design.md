# AFM Points-Table Upgrades — Design Spec

Date: 2026-07-17
Status: Approved (brainstorming), pending implementation plan
Scope: Sub-project **C4** of the AFM feature-parity effort (final part of C). Fidelity:
**curated** subset of the legacy `MeasurementPoints.vue` (768 lines).

## Background

skewnono's `MeasurementPointsTable.vue` (124 lines) shows the detailed per-point rows with a
fixed 8-column layout, a point-chip filter (filter to one measurement point / All), a
filtered/total count, and an inner scroll. The `AfmDetailRow` payload carries ~20 columns
per point (Site ID, X/Y µm, Left/Right/Ref_H + their Valid flags, Method ID, State, Valid,
Pick Up/Sample/Approach Count, Mileage, …); only 8 are shown and there's no search,
column selection, or pagination.

The legacy component adds free-text search, a localStorage-persisted column picker,
pagination, summary tiles, preferred-column ordering, and a CSV export. We port a
**curated** subset.

## Goals

1. **Free-text search** — filter rows whose any *visible* cell contains the query
   (case-insensitive).
2. **Column picker** — choose which available columns to display; default = today's 8;
   selection **persisted** to `localStorage`.
3. **Pagination** — 25 rows per page, replacing the inner scroll.
4. **Summary tiles** — total points, valid points (`Valid === true`), and columns shown.
5. Keep the existing point-chip filter (filter to one measurement point) and the emitted
   `update:selectedPoint`.

## Non-goals

- CSV export — Sub-project A already exports the detailed points.
- Prose/priority tuning beyond a simple preferred → `(nm)` → other column ordering.
- Server-side paging (client-side over the already-loaded rows).

## Design

### Pure logic — `front-dev-home/app/utils/afmPointsTable.ts` (new)

Testable with `node --test` (`import type { AfmDetailRow }` only):

```ts
export interface PointColumn {
  key: string
  label: string
}

// The columns shown by default (today's 8), in order.
export const DEFAULT_POINT_COLUMN_KEYS: string[]
  // ['measurement_point','Point No','X (um)','Y (um)','Left_H (nm)','Right_H (nm)','Ref_H (nm)','State']

// All columns present across the rows, ordered preferred-first, then '(nm)' columns,
// then the rest (each group in first-seen order), with a humanized label per key
// (e.g. 'measurement_point' → 'Site', 'X (um)' → 'X (μm)'; unknown keys title-cased).
export const derivePointColumns = (rows: AfmDetailRow[]): PointColumn[]

// Rows filtered by the selected point (measurement_point === selectedPoint; '' = all)
// then by a case-insensitive substring match on any of the given visible column keys.
export const filterPointRows = (
  rows: AfmDetailRow[],
  selectedPoint: string,
  search: string,
  visibleKeys: string[]
): AfmDetailRow[]

export interface PointsSummary { total: number, valid: number }

// total = rows.length; valid = count where row.Valid === true.
export const pointsSummary = (rows: AfmDetailRow[]): PointsSummary

// Page slice (1-based page, pageSize rows). Clamps page into range; empty rows → [].
export const pagePointRows = (
  rows: AfmDetailRow[],
  page: number,
  pageSize: number
): AfmDetailRow[]
```

A `LABEL_OVERRIDES` map holds the known friendly labels (matching the current 8 plus common
ones); `humanizeKey` title-cases unknown keys.

### Component — `MeasurementPointsTable.vue`

- **Controls row** (in/under the header): a `UInput` search box (debounce not required — the
  data is small); a **column picker** (`USelectMenu` multiple, or a `UDropdownMenu` of
  checkbox items) over `derivePointColumns(data)`, bound to `visibleKeys`.
- **Persistence:** `visibleKeys` initializes from `localStorage` key
  `skewnono:afm.pointColumns` (falling back to `DEFAULT_POINT_COLUMN_KEYS`) and writes back
  on change (client-guarded, wrapped in try/catch like `useAfmCart`). Keys no longer present
  in the current data are ignored when rendering.
- **Summary tiles:** a small row of three tiles — Total points, Valid points, Columns —
  from `pointsSummary(filteredRows)` and `visibleColumns.length`.
- **Filtering:** `filteredRows = filterPointRows(data, selectedPoint, search, visibleKeys)`.
- **Pagination:** `pagePointRows(filteredRows, page, 25)` for the table body; a
  `UPagination` (or prev/next) below the table; `page` resets to 1 when the filter/search
  changes. The inner `max-h`/scroll is removed (25 rows fit).
- **Columns rendered:** `visibleColumns = derivePointColumns(data).filter(c =>
  visibleKeys.includes(c.key))`, preserving the derived order.
- The point-chip filter and `update:selectedPoint` emit are unchanged.
- Cell formatting unchanged (`–` for empty, integers vs 2-dp, else string).

## Error handling & edge cases

- Empty data → existing "No measurement rows" state.
- Search/point-filter yields 0 rows → empty state + summary tiles show 0; pagination hidden.
- `localStorage` unavailable (private mode / SSR) → guarded; falls back to defaults, no throw.
- Stored keys referencing columns absent from the current tool's data → filtered out so the
  table never renders a dead column; if the intersection is empty, fall back to the
  defaults intersected with present columns.
- `page` beyond the last page (after filtering shrinks the set) → clamped by `pagePointRows`
  and reset to 1 on filter change.

## Testing

`node --test` unit tests for `afmPointsTable.ts`:

- `derivePointColumns`: preferred columns come first in order; `(nm)` columns next; others
  last; labels applied (known overrides + title-cased unknowns); dedupes across rows.
- `filterPointRows`: point filter alone; search alone (case-insensitive, matches only
  visible columns — a match in a hidden column does not surface the row); combined; empty
  query returns the point-filtered set.
- `pointsSummary`: total and valid counts (Valid true/false mix); empty → zeros.
- `pagePointRows`: correct slice for page 1/2; last partial page; page clamped when out of
  range; empty input → [].

Component is `.vue` wiring — gated by `npm run typecheck` + `npm run lint` + in-app
verification (search narrows rows; column picker adds/removes columns and persists across a
reload; pagination pages through; tiles update; point-chip filter still works).

## Files touched

- `front-dev-home/app/utils/afmPointsTable.ts` (new)
- `front-dev-home/app/utils/afmPointsTable.test.ts` (new)
- `front-dev-home/app/components/afm/detail/MeasurementPointsTable.vue` (search / picker / pagination / tiles)

## Completion

C4 is the last sub-project of C. With A (export), B (image gallery), and C2/C3/C4 (chart
depth) done, the AFM feature-parity effort (curated) is complete; D (nav/UX polish —
breadcrumb, See-Together progress dialog) remains as optional follow-on.
