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
