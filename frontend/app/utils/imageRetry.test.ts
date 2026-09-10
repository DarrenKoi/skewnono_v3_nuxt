// Pure-logic tests for imageRetry. Run: node --test app/utils/imageRetry.test.ts
//
// The auto-retry exists because the cloud ingress 502s a slow first
// /api/msr-image fetch while Flask finishes it into the MinIO cache — the
// retried URL must therefore reach the SAME server-side cache entry (extra
// query args only, never a path change) while still being a NEW string for
// the browser.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { withRetrySeq } from './imageRetry.ts'

test('seq 0 is the original URL, untouched', () => {
  const url = '/api/msr-image?eqp_ip=1.2.3.4&name=a.jpeg'
  assert.equal(withRetrySeq(url, 0), url)
})

test('a retry appends the seq with the right separator for both URL shapes', () => {
  // msr-image URLs always carry a query; the bare shape is pinned so the
  // helper stays safe for any future asset URL.
  assert.equal(
    withRetrySeq('/api/msr-image?name=a.jpeg', 2),
    '/api/msr-image?name=a.jpeg&retry=2'
  )
  assert.equal(withRetrySeq('/img/a.jpeg', 1), '/img/a.jpeg?retry=1')
})
