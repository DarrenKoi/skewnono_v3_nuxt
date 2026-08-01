import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createPendingChatTurn,
  isPendingTurnForThread
} from './chatTurn.ts'

test('a pending turn keeps one request id across retries', () => {
  const turn = createPendingChatTurn('thread-a', 'alarm reset', () => 'fixed-request-id')
  assert.deepEqual(turn, {
    threadId: 'thread-a',
    content: 'alarm reset',
    requestId: 'fixed-request-id'
  })
  assert.equal(turn.requestId, 'fixed-request-id')
})

test('pending reconciliation is bound to its originating thread', () => {
  const turn = createPendingChatTurn('thread-a', 'alarm reset', () => 'request-a')

  assert.equal(isPendingTurnForThread(turn, 'thread-a'), true)
  assert.equal(isPendingTurnForThread(turn, 'thread-b'), false)
})
