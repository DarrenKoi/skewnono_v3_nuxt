import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { WARM_CEILING_MS, nextWarmState, warmProgressLabel } from './imageWarm.ts'

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
