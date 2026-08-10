import type { ComputedRef } from 'vue'
import type { FocusImageCtx } from '~/composables/useFocusImageCtx'
import { WARM_POLL_MS, type WarmStatus, nextWarmState, warmRetryDelayMs } from '~/utils/imageWarm'

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
 * the tool is saturated is what turns a cap into a stampede. Everything else
 * (dead tool, expired job) still gives up: waiting would not improve it. */
const runWarm = async (
  state: WarmState,
  api: ReturnType<typeof useMsrImageApi>,
  ctx: FocusImageCtx,
  names: string[]
) => {
  const startedAt = Date.now()
  for (let attempt = 0; ; attempt++) {
    try {
      const jobId = await api.startDownloadAll(ctx.eqp_ip, ctx.class_name, ctx.msr, names)
      for (;;) {
        await sleep(WARM_POLL_MS)
        const poll = await api.pollJob(jobId)
        state.done = poll.done
        state.total = poll.total
        state.status = nextWarmState(poll, Date.now() - startedAt)
        if (state.status !== 'warming') return
      }
    } catch (err) {
      // `attempt` counts POST refusals, and a refusal means no job was created
      // — so the retry re-POSTs rather than resuming a poll. There is no
      // job_id to resume.
      const delay = warmRetryDelayMs(err, attempt, Date.now() - startedAt, Math.random())
      if (delay === null) {
        state.status = 'gaveup'
        return
      }
      await sleep(delay)
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
 * the tool being busy is exactly when a cold GET storm must not happen. No
 * job can hold a panel forever even so: WARM_CEILING_MS bounds the total
 * wait — retries included — and anything past it resolves to 'gaveup'.
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
