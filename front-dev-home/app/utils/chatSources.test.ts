import assert from 'node:assert/strict'
import test from 'node:test'

import * as chatSources from './chatSources.ts'

const { formatSourceLabel, normalizeFeedbackInput } = chatSources

test('manual source label includes revision and page', () => {
  assert.equal(formatSourceLabel({
    source_id: 'manual-1', source_type: 'manual', title: 'Alarm Manual',
    snippet: 'Reset procedure', revision: 'R2', occurred_at: null,
    section: 'Alarm', page: 12, region: null, locator: null, score: 0.9
  }), 'Alarm Manual · R2 · p.12')
})

test('non-manual source label includes its occurred date', () => {
  assert.equal(formatSourceLabel({
    source_id: 'email-1', source_type: 'email', title: 'Maintenance Notice',
    snippet: 'Maintenance is scheduled', revision: null,
    occurred_at: '2026-04-02T01:00:00Z', section: 'Notice', page: null,
    region: null, locator: 'internal-email-locator', score: 0.8
  }), 'Maintenance Notice · 2026-04-02')
})

test('feedback removes blank comment and duplicate reasons', () => {
  assert.deepEqual(normalizeFeedbackInput('down', ['wrong_source', 'wrong_source'], '  '), {
    rating: 'down', reasons: ['wrong_source'], comment: null
  })
})

test('feedback keeps allowed reasons in canonical order', () => {
  assert.deepEqual(
    normalizeFeedbackInput('down', ['other', 'not_allowed', 'incorrect', 'other'], ''),
    { rating: 'down', reasons: ['incorrect', 'other'], comment: null }
  )
})

test('feedback trims and limits comments to 500 characters', () => {
  assert.deepEqual(normalizeFeedbackInput('up', [], `  ${'x'.repeat(510)}  `), {
    rating: 'up', reasons: [], comment: 'x'.repeat(500)
  })
})

test('feedback reconciliation updates the reopened thread message by id', () => {
  const reconcileMessageFeedback = Reflect.get(chatSources, 'reconcileMessageFeedback')
  assert.equal(typeof reconcileMessageFeedback, 'function')

  const storedFeedback = {
    rating: 'down' as const,
    reasons: ['wrong_source' as const],
    comment: 'Use the current manual.',
    updated_at: '2026-08-02T00:00:00Z'
  }
  const reopenedMessage = {
    id: 'assistant-1',
    role: 'assistant' as const,
    feedback: null
  }
  const reopenedThread = { id: 'thread-a', messages: [reopenedMessage] }

  assert.equal(reconcileMessageFeedback(
    reopenedThread,
    'thread-a',
    'assistant-1',
    storedFeedback
  ), true)
  assert.deepEqual(reopenedMessage.feedback, storedFeedback)
})

test('feedback reconciliation preserves a different active thread', () => {
  const reconcileMessageFeedback = Reflect.get(chatSources, 'reconcileMessageFeedback')
  assert.equal(typeof reconcileMessageFeedback, 'function')

  const activeMessage = {
    id: 'assistant-b',
    role: 'assistant' as const,
    feedback: null
  }
  const activeThread = { id: 'thread-b', messages: [activeMessage] }

  assert.equal(reconcileMessageFeedback(
    activeThread,
    'thread-a',
    'assistant-a',
    {
      rating: 'up', reasons: [], comment: null,
      updated_at: '2026-08-02T00:00:00Z'
    }
  ), false)
  assert.equal(activeMessage.feedback, null)
})
