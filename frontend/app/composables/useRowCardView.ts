export type RowCardView = 'cards' | 'table'

/**
 * 행 보기 / 표 보기 토글의 저장 상태.
 *
 * 카드가 기본값입니다 — 읽으러 오는 사람이 다수이고, 표는 정렬하거나 엑셀에
 * 붙여넣으려는 사람이 의도적으로 꺼내는 모드입니다. 저장된 값이 깨졌거나
 * 비어 있으면 그 기본값으로 돌아갑니다.
 *
 * 값이 두 글자짜리 리터럴이라 JSON 으로 감싸지 않고 원문자열로 저장합니다
 * (`isEmpty: () => false` — 'cards' 도 지워지지 않고 남아야 합니다).
 */
export const useRowCardView = (stateKey: string, storageKey: string) =>
  usePersistedState<RowCardView>(stateKey, storageKey, {
    default: () => 'cards',
    normalize: parsed => parsed === 'table' ? 'table' : 'cards',
    isEmpty: () => false,
    serialize: value => value,
    deserialize: raw => raw
  })
