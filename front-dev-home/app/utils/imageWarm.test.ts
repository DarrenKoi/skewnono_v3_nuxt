import { describe, it, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  WARM_CEILING_MS,
  nextWarmState,
  warmProgressLabel,
  WARM_RETRY_DELAYS_MS,
  jittered,
  warmErrorCode,
  warmRetryDelayMs
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
  assert.equal(warmRetryDelayMs(rateLimited, 0, 0, 0.5), null)
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
