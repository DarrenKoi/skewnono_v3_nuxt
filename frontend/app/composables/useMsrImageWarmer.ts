import type { ComputedRef } from 'vue'
import type { FocusImageCtx } from '~/composables/useFocusImageCtx'
import {
  WARM_HOLD_MAX_MS,
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
  /** The server job this state tracks, once one was created. Kept across a
   * 'gaveup' so a revisit resumes polling it instead of POSTing a twin. */
  jobId?: string
  /** A runWarm is currently polling this state. */
  active?: boolean
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

/** POST the job (unless `state` already names one), then poll it, writing
 * progress into `state`.
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
 * Two clocks bound the wait. The STALL clock restarts on every progress report
 * and is what every request timeout and retry ladder is sized against: a job
 * that stops advancing for WARM_CEILING_MS is stuck or lost and is given up
 * on. The HOLD clock runs from the start and caps how long the panel is kept
 * blank at WARM_HOLD_MAX_MS, whatever the job is doing — a large HV-SEM
 * parameter is not stuck, but a reviewer should not stare at a spinner for
 * its whole run either. Past it the panel is released and per-image
 * auto-retry covers whatever the job has not reached yet. A resumed run (see
 * useMsrImageWarmer) never holds, so only the stall clock applies to it.
 *
 * Aborting a POST can leave a job the server already created running
 * unattended — it still fills the shared cache, and it only happens at the
 * point we were about to give up anyway. */
const runWarm = async (
  state: WarmState,
  api: ReturnType<typeof useMsrImageApi>,
  ctx: FocusImageCtx,
  names: string[]
) => {
  const startedAt = Date.now()
  let progressAt = startedAt
  const sinceProgress = () => Date.now() - progressAt
  const holding = state.status === 'warming'
  const giveUp = () => {
    state.status = 'gaveup'
  }
  state.active = true
  try {
    let jobId = state.jobId
    for (let postAttempt = 0; jobId === undefined; postAttempt++) {
      const postBudget = remainingBudgetMs(sinceProgress())
      if (postBudget === 0) return giveUp()
      try {
        jobId = await api.startDownloadAll(ctx.eqp_ip, ctx.class_name, ctx.msr, names, postBudget)
      } catch (err) {
        // A refusal means no job was created — so the retry re-POSTs rather
        // than resuming a poll. There is no job_id to resume.
        const delay = warmRetryDelayMs(err, postAttempt, sinceProgress(), Math.random())
        if (delay === null) return giveUp()
        await sleep(delay)
      }
    }
    // From here a job exists, and it is remembered on the state: a run that
    // gives up leaves it there, so a later visit RESUMES this job instead of
    // POSTing a second one for files it is still fetching. Never re-POST: the
    // running one keeps its max_jobs slot, so a second job is a second visit
    // to the tool.
    state.jobId = jobId

    // A retry's backoff REPLACES the next poll interval rather than preceding
    // it. Sleeping both would make one retry cost delay + WARM_POLL_MS while
    // the ladder's ceiling check counted only `delay` — so the panel could
    // outlive the ceiling by a poll interval, which is what this budget exists
    // to stop.
    let wait = WARM_POLL_MS
    for (let pollFailures = 0; ;) {
      await sleep(wait)
      wait = WARM_POLL_MS // reset here, not in the for-update: `continue` runs that
      const pollBudget = remainingBudgetMs(sinceProgress())
      if (pollBudget === 0) return giveUp()
      let poll
      try {
        poll = await api.pollJob(jobId, pollBudget)
      } catch (err) {
        const delay = pollRetryDelayMs(err, pollFailures++, sinceProgress(), Math.random())
        if (delay === null) return giveUp()
        wait = delay
        continue
      }
      pollFailures = 0 // consecutive, so a long job survives scattered hiccups
      // `total` landing counts as progress too: it is the first thing a job
      // reports, before any file has finished.
      if (poll.done > state.done || poll.total !== state.total) progressAt = Date.now()
      state.done = poll.done
      state.total = poll.total
      const next = nextWarmState(poll, sinceProgress())
      if (next !== 'warming') {
        state.status = next
        return
      }
      if (holding && Date.now() - startedAt >= WARM_HOLD_MAX_MS) return giveUp()
    }
  } finally {
    state.active = false
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
 * can hold a panel forever even so: WARM_CEILING_MS gives up on a job that
 * stops making progress, and WARM_HOLD_MAX_MS releases the panel from a job
 * that is merely long — see runWarm.
 *
 * A 'gaveup' is not final for the session. Coming back to that parameter
 * resumes polling the same job in the background (or POSTs one if none was
 * ever created) WITHOUT holding the panel again: the tiles that already
 * painted stay put, and the state flips to 'ready' once the job is done.
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
      const prev = warmStore[k]
      if (prev) {
        // Warmed, warming, or a given-up run that is idle: only the last one
        // gets another go, and it resumes as 'gaveup' (no hold) — see above.
        if (prev.status === 'gaveup' && !prev.active) void runWarm(prev, api, ctx.value, names)
        return
      }
      const state: WarmState = reactive({ status: 'warming', done: 0, total: 0 })
      warmStore[k] = state
      void runWarm(state, api, ctx.value, names)
    },
    { immediate: true }
  )

  return computed(() => warmStore[key.value] ?? IDLE)
}
