// Recipe 현황: the same summary endpoint asked once more for the window just
// before the one on screen, so each KPI can show its change.
//
// Owns the rules both tabs share: nothing is requested until the effective
// window is known (the user's range, else the echo of the server default), the
// comparison is never awaited so it cannot hold the dashboard back, and an
// answer is used only while its echoed dates still match the window on screen
// — a retained one, a failed request, or a failed main request shows no
// comparison rather than a wrong one.
import type { AsyncDataRequestStatus } from '#app'
import { isAnchorIncluded, previousWindow, type WindowedSummary } from '~/utils/recipeStatusDelta'

export interface DateWindow {
  start: string
  end: string
}

/** The part of the main request's parameters that scopes its cache key. */
interface SummaryScope {
  toolType: string
  fabNames?: readonly string[] | null
  lotCd?: string | null
}

export const usePreviousWindowSummary = <T extends WindowedSummary>(opts: {
  /** Cache-key prefix of the feature, e.g. `recipe-tat`. */
  keyPrefix: string
  /** The effective window on screen; empty strings until it is known. */
  dateRange: Ref<DateWindow>
  /** The main request's parameters, so the two cache keys cannot cross scopes. */
  queryParams: Ref<SummaryScope>
  mainStatus: Ref<AsyncDataRequestStatus>
  /** Whether the main summary has landed; the comparison waits for it. */
  mainReady: () => boolean
  /** The backend's anchor date, once the main summary has echoed it. */
  anchorDate: () => string | undefined
  fetch: (window: DateWindow) => Promise<T>
}) => {
  const window = computed<DateWindow | null>(() => {
    const { start, end } = opts.dateRange.value
    return start && end ? previousWindow(start, end) : null
  })

  const key = computed(() => {
    const win = window.value
    if (!win) return `${opts.keyPrefix}:prev:idle`
    const q = opts.queryParams.value
    return `${opts.keyPrefix}:prev:${q.toolType}:${q.fabNames?.join(',') ?? 'ALL'}:${q.lotCd ?? '*'}:${win.start}:${win.end}`
  })

  const { data, status } = useAsyncData(
    () => key.value,
    async () => {
      const win = window.value
      return win ? await opts.fetch(win) : null
    },
    { watch: [key] }
  )

  /** `'pending'` while either request is in flight, the summary once it answers for the window on screen, `undefined` otherwise. */
  const state = computed<'pending' | T | undefined>(() => {
    const win = window.value
    if (opts.mainStatus.value === 'error') return undefined
    if (opts.mainStatus.value === 'pending' || status.value === 'pending' || !opts.mainReady() || !win) return 'pending'
    // useAsyncData types `data` through its pick transform; the handler returns T | null.
    const prev = data.value as T | null | undefined
    if (status.value !== 'success' || !prev || prev.start_date !== win.start || prev.end_date !== win.end) return undefined
    return prev
  })

  /** The window on screen still contains the unfinished anchor day. */
  const anchorIncluded = computed(() => isAnchorIncluded(opts.dateRange.value.end, opts.anchorDate() ?? ''))

  return { window, state, anchorIncluded }
}
