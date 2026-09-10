import type { SortingState } from '@tanstack/vue-table'

/**
 * What `EbeamFailIssueRankingTable` is currently showing.
 *
 * Panels that render something beside the table need its view, not the raw
 * rows: the TAT view's bar chart draws exactly these rows in exactly this
 * order, so a chart sorted by one measure can never sit above a table sorted
 * by another. Emitted as one object rather than three separate events, so a
 * listener can never observe a half-updated view.
 *
 * It lives here rather than in the component because `<script setup>` cannot
 * export types.
 */
export interface RankingTableState<Row> {
  search: string
  sorting: SortingState
  sortedRows: Row[]
}
