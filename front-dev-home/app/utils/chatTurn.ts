export interface PendingChatTurn {
  threadId: string
  content: string
  requestId: string
}

export const createPendingChatTurn = (
  threadId: string,
  content: string,
  makeId: () => string = () => crypto.randomUUID()
): PendingChatTurn => ({ threadId, content, requestId: makeId() })

export const isPendingTurnForThread = (
  turn: PendingChatTurn | null,
  threadId: string | null
): turn is PendingChatTurn => turn !== null && turn.threadId === threadId
