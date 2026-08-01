import assert from 'node:assert/strict'
import test from 'node:test'

import {
  completeThreadTurn,
  createPendingChatTurn,
  failThreadTurn,
  getThreadTurnState,
  startThreadTurn,
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

test('a failed A turn survives a B send and retries with the original A identity', () => {
  const turnA = createPendingChatTurn('thread-a', 'alarm A', () => 'request-a')
  const turnB = createPendingChatTurn('thread-b', 'alarm B', () => 'request-b')

  let states = startThreadTurn({}, turnA)
  states = failThreadTurn(states, turnA, 'A failed')
  states = startThreadTurn(states, turnB)
  states = completeThreadTurn(states, turnB)

  const failedA = getThreadTurnState(states, 'thread-a')
  assert.equal(failedA?.status, 'failed')
  assert.equal(failedA?.errorMessage, 'A failed')
  assert.deepEqual(failedA?.turn, {
    threadId: 'thread-a',
    content: 'alarm A',
    requestId: 'request-a'
  })

  states = startThreadTurn(states, failedA!.turn)
  const retryingA = getThreadTurnState(states, 'thread-a')
  assert.equal(retryingA?.status, 'pending')
  assert.equal(retryingA?.errorMessage, null)
  assert.equal(retryingA?.turn.requestId, 'request-a')
})
