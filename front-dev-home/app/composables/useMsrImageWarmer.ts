import type { ComputedRef } from 'vue'
import type { FocusImageCtx } from '~/composables/useFocusImageCtx'
import {
  WARM_POLL_MS,
  type WarmStatus,
  nextWarmState,
  pollRetryDelayMs,
  remainingBudgetMs,
  warmRetryDelayMs
} from '~/utils/imageWarm'

/** What to warm: the scope `id` names the unit (the active parameter) and
 * `names` its image files. The id — not the name list — keys the store, so
 * the watch key stays a few dozen bytes and never re-derives the names. */
export interface WarmScope {
  id: string
  names: string[]
}

/** What a consumer needs to decide between "hold" and "show the image". */
export interface WarmState {
  status: WarmStatus
  done: number
  total: number
}

// (ctx, scope-id) → the job's live state. Module-level on purpose, twice over:
// navigating away and back must not queue the same tool work again, and the
// poll loop has to outlive the component that started it. SPA-only (`ssr:
// false`), so there is no cross-request leak to worry about.
//
// `reactive`, not a Map: the store is written by the watch below and read by
// the computed it returns on the SAME tick, and a plain Map would let that
// computed cache `idle` with nothing to invalidate it.
const warmStore = reactive<Record<string, WarmState>>({})

const IDLE: WarmState = { status: 'idle', done: 0, total: 0 }

const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

/** POST the job, then poll it to completion, writing progress into `state`.
 *
 * A refused POST (the 2-job cap) is WAITED OUT rather than surfaced. Giving up
 * used to look harmless — the per-image cold GET still runs — but that path has
 * no session budget at all, so releasing the whole panel at the exact moment
 * the tool is saturated is what turns a cap into a stampede.
 *
 * The two failure paths are handled SEPARATELY because their premises differ.
 * A POST that fails created no job, so there is nothing to wait for and only
 * the self-clearing cap is worth retrying. A poll that fails is asking about a
 * job that exists and is already reading the tool, so the failure says nothing
 * about whether waiting will pay off — only a job that is definitively gone
 * ends the wait. One shared `try` used to collapse both into "give up", which
 * let a single rate-limited poll release the panel mid-job.
 *
 * Every request is capped at the REMAINING ceiling budget, so a call that
 * never answers cannot hold the panel past WARM_CEILING_MS. Aborting a POST
 * can leave a job the server already created running unattended — it still
 * fills the shared cache, and it only happens at the point we were about to
 * give up anyway. */
const runWarm = async (
  state: WarmState,
  api: ReturnType<typeof useMsrImageApi>,
  ctx: FocusImageCtx,
  names: string[]
) => {
  const startedAt = Date.now()
  const elapsed = () => Date.now() - startedAt
  const giveUp = () => {
    state.status = 'gaveup'
  }

  for (let postAttempt = 0; ; postAttempt++) {
    let jobId: string
    const postBudget = remainingBudgetMs(elapsed())
    if (postBudget === 0) return giveUp()
    try {
      jobId = await api.startDownloadAll(ctx.eqp_ip, ctx.class_name, ctx.msr, names, postBudget)
    } catch (err) {
      // `postAttempt` counts POST refusals, and a refusal means no job was
      // created — so the retry re-POSTs rather than resuming a poll. There is
      // no job_id to resume.
      const delay = warmRetryDelayMs(err, postAttempt, elapsed(), Math.random())
      if (delay === null) return giveUp()
      await sleep(delay)
      continue
    }

    // From here a job exists. Never re-POST: the running one keeps its
    // max_jobs slot, so a second job is a second visit to the tool for files
    // the first is already fetching.
    //
    // A retry's backoff REPLACES the next poll interval rather than preceding
    // it. Sleeping both would make one retry cost delay + WARM_POLL_MS while
    // the ladder's ceiling check counted only `delay` — so the panel could
    // outlive the ceiling by a poll interval, which is what this budget exists
    // to stop.
    let wait = WARM_POLL_MS
    for (let pollFailures = 0; ;) {
      await sleep(wait)
      wait = WARM_POLL_MS // reset here, not in the for-update: `continue` runs that
      const pollBudget = remainingBudgetMs(elapsed())
      if (pollBudget === 0) return giveUp()
      let poll
      try {
        poll = await api.pollJob(jobId, pollBudget)
      } catch (err) {
        const delay = pollRetryDelayMs(err, pollFailures++, elapsed(), Math.random())
        if (delay === null) return giveUp()
        wait = delay
        continue
      }
      pollFailures = 0 // consecutive, so a long job survives scattered hiccups
      state.done = poll.done
      state.total = poll.total
      state.status = nextWarmState(poll, elapsed())
      if (state.status !== 'warming') return
    }
  }
}

/**
 * Warm the server-side image cache for the images the user is about to click,
 * and report when it is ready.
 *
 * POST /api/msr-images with a `names` scope runs the tool-FTP fetch of exactly
 * those files server-side and writes them into the shared cache. Scoped to the
 * ACTIVE PARAMETER, not the whole MSR directory — a parameter switch warms the
 * newly active set, and images of parameters never opened are never pulled
 * from the tool.
 *
 * The returned state is what lets a panel WAIT instead of racing the job. A
 * cold /api/msr-image GET does the FTP fetch inside the request, which the
 * cloud ingress 502s; asking only once the job reports `done` turns that into
 * a cache hit, so there is no failed request for the browser to log. See
 * utils/imageWarm.ts for why hiding the error client-side is not an option.
 *
 * A refusal (429) is retried with backoff and the panel keeps holding, since
 * the tool being busy is exactly when a cold GET storm must not happen, and a
 * poll that fails while the job runs is retried for the same reason. No job
 * can hold a panel forever even so: WARM_CEILING_MS bounds the total wait —
 * retries and unanswered requests included — and anything past it resolves to
 * 'gaveup'.
 */
export const useMsrImageWarmer = (
  ctx: ComputedRef<FocusImageCtx>,
  scope: ComputedRef<WarmScope>
): ComputedRef<WarmState> => {
  const api = useMsrImageApi()

  const key = computed(() => {
    const { eqp_ip, class_name, msr } = ctx.value
    return `${eqp_ip}|${class_name}|${msr}|${scope.value.id}`
  })

  // The name COUNT is a watch source but not part of the key. The tool context
  // and the measurement rows arrive from two different requests in either
  // order, so keying on the context alone means a run where the context lands
  // first sees `names` still empty, bails, and — the key never changing again —
  // never warms at all. Whether that happened was pure request-order luck.
  // `warmStore[k]` still does the deduping, so a later count change re-enters
  // the watch and finds the job already running.
  watch(
    [key, () => scope.value.names.length],
    ([k]) => {
      const { eqp_ip, class_name, msr } = ctx.value
      const { names } = scope.value
      if (!eqp_ip || !class_name || !msr || !names.length) return
      if (warmStore[k]) return // already warmed, or warming, this session
      const state: WarmState = reactive({ status: 'warming', done: 0, total: 0 })
      warmStore[k] = state
      void runWarm(state, api, ctx.value, names)
    },
    { immediate: true }
  )

  return computed(() => warmStore[key.value] ?? IDLE)
}
