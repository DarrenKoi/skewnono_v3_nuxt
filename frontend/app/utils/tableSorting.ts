/**
 * UTable options for a table that sorts its own rows.
 *
 * `manualSorting: true` IS THE LOAD-BEARING LINE. Without it a table's own
 * sort is **dead code**: UTable always installs `getSortedRowModel()`, so the
 * array you carefully ordered gets re-sorted by TanStack's `sortingFns.basic`.
 * `compareBasic(null, x)` returns -1, which makes null the smallest value
 * (`sortUndefined` only covers `undefined`, never `null`), so every
 * below-sample-floor row climbs to the top of an ascending sort — "we cannot
 * judge this tool" reads as "the best tool", which is precisely the misreading
 * the sample floor exists to prevent. Descending happens to agree, which is
 * why the bug hid.
 *
 * The flag bypasses `getSortedRowModel()` wholesale (table-core:
 * `RowSorting.getSortedRowModel` returns `getPreSortedRowModel()` when
 * `manualSorting`), leaving the component's own comparator as the only sort.
 * Header buttons still update `sorting` state; the component reads it.
 *
 * Shared because this rationale is the kind that gets deleted by someone
 * tidying "an obviously redundant option". It was copied into two fleet tables
 * and had ALREADY forked by 2026-08-09 — the fail-issue copy had lost the
 * bypass paragraph, which is the half that explains why the line cannot go.
 */
export const MANUAL_SORTING_OPTIONS = {
  enableMultiSort: false,
  enableSortingRemoval: false,
  manualSorting: true
} as const
