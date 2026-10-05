// Recipe 현황: the same summary endpoint asked once more for the window just
// before the one on screen, so each KPI can show its change.
//
// Owns the three rules both tabs share: nothing is requested until the
// effective window is known (the user's range, else the echo of the server
// default), the comparison is never awaited so it cannot hold the dashboard
// back, and an answer is used only while its echoed dates still match the
// window on screen — a retained one, or a failed request, shows no comparison
// rather than a wrong one.
import type { AsyncDataRequestStatus } from '#app'
import { previousWindow } from '~/utils/recipeStatusDelta'

interface WindowedSummary {
  start_date: string | null
  end_date: string | null
}

export interface DateWindow {
  start: string
  end: string
}

export const usePreviousWindowSummary = <T extends WindowedSummary>(opts: {
  /** Cache-key prefix of the feature, e.g. `recipe-tat`. */
  keyPrefix: string
  /** The effective window on screen; empty strings until it is known. */
  dateRange: Ref<DateWindow>
  /** The main request's scope (tool, fabs, lot) so the two keys cannot cross. */
  scope: () => string
  mainStatus: Ref<AsyncDataRequestStatus>
  /** Whether the main summary has landed; the comparison waits for it. */
  mainReady: () => boolean
  fetch: (window: DateWindow) => Promise<T>
}) => {
  const window = computed<DateWindow | null>(() => {
    const { start, end } = opts.dateRange.value
    return start && end ? previousWindow(start, end) : null
  })

  const key = computed(() => {
    const win = window.value
    return win
      ? `${opts.keyPrefix}:prev:${opts.scope()}:${win.start}:${win.end}`
      : `${opts.keyPrefix}:prev:idle`
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
    if (opts.mainStatus.value === 'pending' || status.value === 'pending' || !opts.mainReady() || !win) return 'pending'
    // useAsyncData types `data` through its pick transform; the handler returns T | null.
    const prev = data.value as T | null | undefined
    if (status.value !== 'success' || !prev || prev.start_date !== win.start || prev.end_date !== win.end) return undefined
    return prev
  })

  return { window, state }
}
