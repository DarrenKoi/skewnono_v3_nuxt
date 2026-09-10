import { describe, it, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  WARM_CEILING_MS,
  nextWarmState,
  warmProgressLabel,
  WARM_RETRY_DELAYS_MS,
  jittered,
  warmErrorCode,
  isWarmRefusal,
  warmRetryDelayMs,
  pollRetryDelayMs,
  remainingBudgetMs
} from './imageWarm.ts'

describe('nextWarmState', () => {
  it('holds at 이미지 준비 while the job is still running', () => {
    assert.equal(
      nextWarmState({ status: 'running', done: 3, total: 40 }, 1200),
      'warming'
    )
  })

  it('releases the image the moment the job reports done', () => {
    assert.equal(
      nextWarmState({ status: 'done', done: 40, total: 40 }, 1200),
      'ready'
    )
  })

  // A failed warm must NOT keep the panel hidden: the per-image request path
  // (cache-miss fetch + auto-retry) is still there and may well succeed.
  it('gives up when the job errors', () => {
    assert.equal(
      nextWarmState({ status: 'error', done: 2, total: 40 }, 1200),
      'gaveup'
    )
  })

  // The ceiling is what stops a stuck job from hiding the image forever.
  it('gives up once the ceiling passes even while still running', () => {
    assert.equal(
      nextWarmState({ status: 'running', done: 3, total: 40 }, WARM_CEILING_MS),
      'gaveup'
    )
    assert.equal(
      nextWarmState({ status: 'running', done: 3, total: 40 }, WARM_CEILING_MS + 1),
      'gaveup'
    )
  })

  it('still holds one millisecond short of the ceiling', () => {
    assert.equal(
      nextWarmState({ status: 'running', done: 3, total: 40 }, WARM_CEILING_MS - 1),
      'warming'
    )
  })

  // done wins over the ceiling — a job that landed on the last poll is ready,
  // not given up on.
  it('prefers a finished job over an expired ceiling', () => {
    assert.equal(
      nextWarmState({ status: 'done', done: 40, total: 40 }, WARM_CEILING_MS * 3),
      'ready'
    )
  })
})

describe('warmProgressLabel', () => {
  it('counts files once the job has reported its size', () => {
    assert.equal(warmProgressLabel(12, 40), '이미지를 준비하는 중입니다. 12/40')
  })

  // total starts at 0: the server-side listing that determines it has not run
  // yet, so a "12/0" would be a lie about the job's size.
  it('omits the count while the job size is still unknown', () => {
    assert.equal(warmProgressLabel(0, 0), '이미지를 준비하는 중입니다.')
  })
})

// Pure-logic tests for the warm-job retry policy.
//
// The policy exists because a refused warm job used to become 'gaveup', which
// releases every held <img> at once — so the moment the tool is busiest, the
// screen fires N unbudgeted cold GETs at it. Waiting out the refusal is the
// whole point, and waiting out the WRONG 429 (the /api/* rate limit) would
// make a throttled client send more.

const refusal = { statusCode: 429, data: { code: 'too_many_jobs' } }
const rateLimited = { statusCode: 429, data: {} }

test('the job-cap refusal is recognised through the FetchError body', () => {
  assert.equal(warmErrorCode(refusal), 'too_many_jobs')
  assert.equal(warmErrorCode({ response: { status: 429 }, data: { code: 'too_many_jobs' } }), 'too_many_jobs')
})

test('a rate-limit 429 carries no job code, so it is NOT a refusal', () => {
  // Same status, opposite response: retrying a throttled client sends more.
  assert.equal(warmErrorCode(rateLimited), undefined)
  assert.equal(isWarmRefusal(rateLimited), false)
  assert.equal(warmRetryDelayMs(rateLimited, 0, 0, 0.5), null)
})

// The refusal is a 429 AND the body code — either axis alone is a guess. The
// code alone is what shipped, and the reason this test exists is that the very
// argument for the code check ("not every 429 is the same 429") says the
// converse too: not every `too_many_jobs` would be a 429 if some future path
// put that code on a 5xx.
test('the refusal needs BOTH the status and the code', () => {
  assert.equal(isWarmRefusal(refusal), true)
  assert.equal(isWarmRefusal({ response: { status: 429 }, data: { code: 'too_many_jobs' } }), true)

  // The code on anything but a 429 is not the job cap answering.
  assert.equal(isWarmRefusal({ statusCode: 500, data: { code: 'too_many_jobs' } }), false)
  assert.equal(isWarmRefusal({ response: { status: 503 }, data: { code: 'too_many_jobs' } }), false)
  // No status at all: the request never reached a server (network, abort).
  assert.equal(isWarmRefusal({ data: { code: 'too_many_jobs' } }), false)
})

test('only a real refusal earns a retry', () => {
  assert.equal(warmRetryDelayMs({ statusCode: 500, data: { code: 'too_many_jobs' } }, 0, 0, 0.5), null)
  assert.equal(warmRetryDelayMs({ data: { code: 'too_many_jobs' } }, 0, 0, 0.5), null)
})

test('a refusal retries on the configured backoff ladder', () => {
  // rand = 0.5 is the midpoint, so jitter cancels and the base shows through.
  assert.equal(warmRetryDelayMs(refusal, 0, 0, 0.5), WARM_RETRY_DELAYS_MS[0])
  assert.equal(warmRetryDelayMs(refusal, 1, 0, 0.5), WARM_RETRY_DELAYS_MS[1])
  assert.equal(warmRetryDelayMs(refusal, 2, 0, 0.5), WARM_RETRY_DELAYS_MS[2])
})

test('the ladder ends rather than repeating its last rung forever', () => {
  assert.equal(warmRetryDelayMs(refusal, WARM_RETRY_DELAYS_MS.length, 0, 0.5), null)
})

test('a non-429 failure gives up immediately', () => {
  // A dead tool or an expired job does not improve by waiting.
  assert.equal(warmRetryDelayMs(new Error('network down'), 0, 0, 0.5), null)
})

test('the ceiling wins over the ladder, and is checked BEFORE sleeping', () => {
  // Sleeping 4s only to then give up would hold the panel for nothing.
  assert.equal(warmRetryDelayMs(refusal, 0, WARM_CEILING_MS, 0.5), null)
  assert.equal(warmRetryDelayMs(refusal, 2, WARM_CEILING_MS - 1000, 0.5), null)
})

test('jitter stays inside +/-25% and moves with rand', () => {
  // Several users refused in the same instant must not retry in lockstep.
  assert.equal(jittered(1000, 0), 750)
  assert.equal(jittered(1000, 0.5), 1000)
  assert.equal(jittered(1000, 1), 1250)
})

// Pure-logic tests for the POLL failure policy, which is the opposite of the
// POST one. A POST that fails created no job, so there is nothing to wait for.
// A poll that fails is asking about a job that EXISTS and is already reading
// the tool — giving up there releases the panel into unbudgeted cold GETs at
// the one moment the tool is provably busy on our behalf.

const jobGone = { statusCode: 404, data: { code: 'unknown_job' } }

test('a rate-limited poll keeps waiting instead of releasing the panel', () => {
  // A generic/proxy 429 says nothing about the already-running job. The answer
  // is to ask again, not to release every held image into a cold-fetch storm.
  assert.equal(pollRetryDelayMs(rateLimited, 0, 0, 0.5), WARM_RETRY_DELAYS_MS[0])
})

test('a transient network failure on a poll keeps waiting too', () => {
  assert.equal(pollRetryDelayMs(new Error('network down'), 0, 0, 0.5), WARM_RETRY_DELAYS_MS[0])
})

test('a job that is gone for good ends the wait', () => {
  // Nothing will ever fill this cache: re-polling forever would hold the panel
  // for a job that no longer exists.
  assert.equal(pollRetryDelayMs(jobGone, 0, 0, 0.5), null)
  assert.equal(
    pollRetryDelayMs({ response: { status: 404 }, data: { code: 'unknown_job' } }, 0, 0, 0.5),
    null
  )
})

test('a bare 404 is our fault, not proof the job died', () => {
  // Both axes, for the same reason isWarmRefusal needs both: a 404 from a
  // proxy or a mis-mounted route says nothing about the job, and treating it
  // as a dead job releases the panel into the storm this loop prevents.
  assert.equal(pollRetryDelayMs({ statusCode: 404, data: {} }, 0, 0, 0.5), WARM_RETRY_DELAYS_MS[0])
  // And the code without the status is not poll_job_route answering either.
  assert.equal(
    pollRetryDelayMs({ data: { code: 'unknown_job' } }, 0, 0, 0.5),
    WARM_RETRY_DELAYS_MS[0]
  )
})

test('consecutive poll failures walk the same ladder and then stop', () => {
  assert.equal(pollRetryDelayMs(rateLimited, 1, 0, 0.5), WARM_RETRY_DELAYS_MS[1])
  assert.equal(pollRetryDelayMs(rateLimited, 2, 0, 0.5), WARM_RETRY_DELAYS_MS[2])
  assert.equal(pollRetryDelayMs(rateLimited, WARM_RETRY_DELAYS_MS.length, 0, 0.5), null)
})

test('the poll ladder is bounded by the SAME ceiling, not a second one', () => {
  assert.equal(pollRetryDelayMs(rateLimited, 0, WARM_CEILING_MS, 0.5), null)
  assert.equal(pollRetryDelayMs(rateLimited, 2, WARM_CEILING_MS - 1000, 0.5), null)
})

// The ceiling is only a ceiling if it also bounds a request that never answers
// — WARM_CEILING_MS is documented as "longest the panel holds an image back",
// and before this it was only ever checked between responses.

test('the remaining budget is what a request may take, and never goes negative', () => {
  assert.equal(remainingBudgetMs(0), WARM_CEILING_MS)
  assert.equal(remainingBudgetMs(1000), WARM_CEILING_MS - 1000)
  assert.equal(remainingBudgetMs(WARM_CEILING_MS), 0)
  // A budget past the ceiling is spent, not owed: a negative timeout would be
  // handed straight to $fetch.
  assert.equal(remainingBudgetMs(WARM_CEILING_MS * 2), 0)
})
