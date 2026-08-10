// Pure policy for "is the server-side image cache ready for this parameter?"
// (useMsrImageWarmer wires it to the POST /api/msr-images job and timers; this
// module stays importable by `npm test`).
//
// WHY THIS EXISTS — the console 502 is not a symptom to hide, it is a race.
// /api/msr-image does the tool-FTP fetch INSIDE the GET when the file is not
// cached yet, and on the cloud the ingress kills that slow request and hands
// the browser a 502. The browser logs every failed subresource load, and it
// logs a failed fetch() identically (verified in Chrome 2026-08-03) — so no
// client-side request style can silence it. The only cure is to not issue a
// request that fails: wait until the warm job has pulled the parameter's
// images into the cache, THEN let the <img> ask for one. imageRetry.ts stays
// as the safety net for everything this gate cannot cover.

/** How often the warm job is polled while it runs. */
export const WARM_POLL_MS = 600

/** Longest the SEM panel will hold an image back waiting for the warm job.
 * Past this the image is requested anyway and the auto-retry takes over — a
 * stuck or lost job must never hide the panel forever. */
export const WARM_CEILING_MS = 15_000

/** 'warming' — hold the image; anything else — request it now. */
export type WarmStatus = 'idle' | 'warming' | 'ready' | 'gaveup'

export interface WarmPoll {
  status: 'running' | 'done' | 'error'
  done: number
  total: number
}

/**
 * The state one poll implies. `elapsedMs` is measured from the POST, so a job
 * that outlives the ceiling releases the image instead of holding it.
 *
 * 'gaveup' is not a failure the user needs to see: it only means "stop waiting
 * and go ask for the image", which is exactly the pre-gate behaviour.
 */
export const nextWarmState = (poll: WarmPoll, elapsedMs: number): WarmStatus => {
  if (poll.status === 'done') return 'ready'
  if (poll.status === 'error') return 'gaveup'
  return elapsedMs >= WARM_CEILING_MS ? 'gaveup' : 'warming'
}

/** Panel copy while warming. `total` is 0 until the server-side listing lands,
 * and a "12/0" would misreport the job's size, so the count waits for it. */
export const warmProgressLabel = (done: number, total: number): string =>
  total > 0
    ? `이미지를 준비하는 중입니다. ${done}/${total}`
    : '이미지를 준비하는 중입니다.'

/** Waits before re-POSTing a refused warm job, in order. Sized so the whole
 * ladder fits inside WARM_CEILING_MS with polling time to spare. */
export const WARM_RETRY_DELAYS_MS = [1000, 2000, 4000] as const

/** The `code` a rejected $fetch carries, whatever shape Nuxt hands us.
 *
 * Status alone cannot decide this. `/api/*` has an application-wide 20 req/5s
 * limit that also answers 429, and warm polling at 600ms can reach it — but
 * only the job-cap refusal carries `too_many_jobs` (routes.py). Retrying the
 * other 429 would have a throttled client send more. */
export const warmErrorCode = (err: unknown): string | undefined =>
  (err as { data?: { code?: string } })?.data?.code

/** `baseMs` spread over +/-25%. `rand` is a caller-supplied [0,1) so the
 * policy stays a pure function; the caller passes Math.random(). Several
 * users refused in the same instant must not retry in lockstep. */
export const jittered = (baseMs: number, rand: number): number =>
  Math.round(baseMs * (0.75 + rand * 0.5))

/**
 * How long to wait before re-POSTing, or `null` to give up.
 *
 * `null` releases the held images to the cold-GET path, which is the old
 * behaviour — so every `null` here is a decision to accept that load.
 */
export const warmRetryDelayMs = (
  err: unknown,
  attempt: number,
  elapsedMs: number,
  rand: number
): number | null => {
  if (warmErrorCode(err) !== 'too_many_jobs') return null
  // Indexing past the ladder yields undefined, which IS the "stop" signal —
  // one check instead of a separate length guard, and no non-null assertion.
  const base = WARM_RETRY_DELAYS_MS[attempt]
  if (base === undefined) return null
  const delay = jittered(base, rand)
  // Checked before sleeping: waiting 4s only to then give up would hold the
  // panel for nothing.
  if (elapsedMs + delay >= WARM_CEILING_MS) return null
  return delay
}
