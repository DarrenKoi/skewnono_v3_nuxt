export interface PendingChatTurn {
  content: string
  requestId: string
}

export const createPendingChatTurn = (
  content: string,
  makeId: () => string = () => crypto.randomUUID()
): PendingChatTurn => ({ content, requestId: makeId() })
