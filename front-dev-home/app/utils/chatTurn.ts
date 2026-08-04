import { generateUuid } from './uuid.ts'

export interface PendingChatTurn {
  threadId: string
  content: string
  requestId: string
}

export interface ThreadTurnState {
  turn: PendingChatTurn
  status: 'pending' | 'failed'
  errorMessage: string | null
}

export type ThreadTurnStates = Record<string, ThreadTurnState>

export const createPendingChatTurn = (
  threadId: string,
  content: string,
  makeId: () => string = generateUuid
): PendingChatTurn => ({ threadId, content, requestId: makeId() })

export const isPendingTurnForThread = (
  turn: PendingChatTurn | null,
  threadId: string | null
): turn is PendingChatTurn => turn !== null && turn.threadId === threadId

export const getThreadTurnState = (
  states: ThreadTurnStates,
  threadId: string | null
): ThreadTurnState | null => threadId === null ? null : states[threadId] ?? null

export const startThreadTurn = (
  states: ThreadTurnStates,
  turn: PendingChatTurn
): ThreadTurnStates => ({
  ...states,
  [turn.threadId]: { turn, status: 'pending', errorMessage: null }
})

export const failThreadTurn = (
  states: ThreadTurnStates,
  turn: PendingChatTurn,
  errorMessage: string
): ThreadTurnStates => {
  const current = states[turn.threadId]
  if (current?.turn.requestId !== turn.requestId) return states
  return {
    ...states,
    [turn.threadId]: { turn, status: 'failed', errorMessage }
  }
}

export const completeThreadTurn = (
  states: ThreadTurnStates,
  turn: PendingChatTurn
): ThreadTurnStates => {
  if (states[turn.threadId]?.turn.requestId !== turn.requestId) return states
  const { [turn.threadId]: _completed, ...remaining } = states
  return remaining
}
