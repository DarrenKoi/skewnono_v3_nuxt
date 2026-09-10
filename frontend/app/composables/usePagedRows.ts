// `computed`/`toValue` are Nuxt auto-imports in app code, but importing them
// explicitly is what lets `node --test` load this file directly — the unit
// tests run outside the Nuxt build. `useFocusImageCtx.ts` does the same.
import { computed, toValue, type MaybeRefOrGetter, type Ref } from 'vue'

/** The 25/50/100 selector four tables offer. Not every table wants it — the
 *  device-statistics card grid pages by 12 — so it is an export, not a default. */
export const PAGE_SIZE_OPTIONS = [
  { label: '25 / page', value: '25' },
  { label: '50 / page', value: '50' },
  { label: '100 / page', value: '100' }
]

export interface PagedRows<T> {
  /** Row count before paging — what "of N" in the footer means. */
  total: Ref<number>
  pageCount: Ref<number>
  /** 1-based index of the first row on this page; 0 when there are none. */
  pageStart: Ref<number>
  pageEnd: Ref<number>
  pagedRows: Ref<T[]>
}

/**
 * Slice already-filtered, already-sorted rows into the current page.
 *
 * Four tables had re-derived this same arithmetic. It is small but not
 * trivially right: `pageCount` floors at 1 so an empty table still reads
 * "Page 1 / 1" instead of "1 / 0", and `pageStart` is 0 rather than 1 when
 * there are no rows, so the footer says "0–0 of 0".
 *
 * Deliberately NOT included: resetting `page` to 1. Callers disagree about
 * what should trigger it (a search change, a new cache key, a fab switch) and
 * one of them mirrors the page into the URL query, so owning the reset here
 * would fight those. Pass in the `page` ref and keep the watcher at the call
 * site.
 */
export const usePagedRows = <T>(
  rows: MaybeRefOrGetter<readonly T[]>,
  pageSize: MaybeRefOrGetter<number>,
  page: Ref<number>
): PagedRows<T> => {
  const total = computed(() => toValue(rows).length)
  const size = computed(() => toValue(pageSize))

  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
  const pageStart = computed(() =>
    total.value === 0 ? 0 : ((page.value - 1) * size.value) + 1
  )
  const pageEnd = computed(() => Math.min(page.value * size.value, total.value))

  const pagedRows = computed(() => {
    const start = (page.value - 1) * size.value
    return toValue(rows).slice(start, start + size.value)
  })

  return { total, pageCount, pageStart, pageEnd, pagedRows }
}
