import assert from 'node:assert/strict'
import test from 'node:test'

import { createPendingChatTurn } from './chatTurn.ts'

test('a pending turn keeps one request id across retries', () => {
  const turn = createPendingChatTurn('alarm reset', () => 'fixed-request-id')
  assert.deepEqual(turn, { content: 'alarm reset', requestId: 'fixed-request-id' })
  assert.equal(turn.requestId, 'fixed-request-id')
})
