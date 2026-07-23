import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { downloadErrorMessage } from './useMsrImageApi.ts'

// $fetch rejects with a FetchError carrying the parsed JSON body on `data`.
const fetchError = (statusCode: number, body: { error?: string, code?: string }) =>
  Object.assign(new Error(`[POST] failed with status ${statusCode}`), { statusCode, data: body })

describe('downloadErrorMessage', () => {
  it('translates the max-concurrent-jobs refusal into something actionable', () => {
    // The backend answers 429 with an English machine code; a user reading the
    // gallery needs to know it is transient and worth retrying.
    const msg = downloadErrorMessage(fetchError(429, { error: 'too many active downloads', code: 'too_many_jobs' }))
    assert.match(msg, /최대/)
  })

  it('explains an expired job rather than echoing "unknown job"', () => {
    const msg = downloadErrorMessage(fetchError(404, { error: 'unknown job', code: 'unknown_job' }))
    assert.match(msg, /만료/)
  })

  it('reports an unreachable tool as a connection problem', () => {
    const msg = downloadErrorMessage(fetchError(503, { error: 'tool listing failed', code: 'office_source_unavailable' }))
    assert.match(msg, /연결/)
  })

  it('falls back to the server text plus status for an unmapped code', () => {
    // Unknown codes must still say something concrete — never swallow the
    // detail the backend went to the trouble of sending.
    const msg = downloadErrorMessage(fetchError(500, { error: 'boom', code: 'something_new' }))
    assert.match(msg, /boom/)
    assert.match(msg, /500/)
  })

  it('uses the raw message when there is no JSON body (network failure)', () => {
    assert.match(downloadErrorMessage(new Error('Failed to fetch')), /Failed to fetch/)
  })

  it('never returns an empty string for a thrown non-error', () => {
    // A bare `throw 'x'` or an undefined rejection must not render a blank
    // error banner, which reads as "something broke but we won't say what".
    assert.ok(downloadErrorMessage(undefined).length > 0)
    assert.ok(downloadErrorMessage({}).length > 0)
  })
})
