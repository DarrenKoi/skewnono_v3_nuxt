import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  FAIL_INDEX_CEIL,
  FAIL_INDEX_FLOOR,
  failEquipmentSignals,
  isIndexConclusive
} from './failEquipmentSignals.ts'

const percentiles = {
  recipe_count: { p10: 4, p25: 8, p50: 12, p75: 18, p90: 24 }
}

const row = (over: Partial<Parameters<typeof failEquipmentSignals>[0]> = {}) => ({
  index: null,
  index_low: null,
  index_high: null,
  recipe_count: 12,
  top_recipe_share: 0.2,
  ...over
})

test('a tool whose interval clears 1.0 and exceeds the ceiling is flagged weak', () => {
  assert.deepEqual(
    failEquipmentSignals(
      row({ index: 1.8, index_low: 1.52, index_high: 2.11 }),
      percentiles
    ),
    ['weak']
  )
})

test('an interval that straddles 1.0 yields no verdict however large the index', () => {
  // 지수만 보면 취약이지만 구간이 1.0 을 걸칩니다 — 잡음과 구별되지 않습니다.
  assert.deepEqual(
    failEquipmentSignals(
      row({ index: 2.4, index_low: 0.88, index_high: 6.1 }),
      percentiles
    ),
    []
  )
})

test('a conclusive interval below the ceiling is still not worth flagging', () => {
  // 구간은 1.0 을 넘겼지만 효과 크기가 작습니다. 통계적 유의와 실무적
  // 중요도는 다른 질문이고, 배지는 둘 다 요구합니다.
  assert.deepEqual(
    failEquipmentSignals(
      row({ index: 1.1, index_low: 1.02, index_high: 1.19 }),
      percentiles
    ),
    []
  )
})

test('a genuinely good tool is flagged healthy', () => {
  assert.deepEqual(
    failEquipmentSignals(
      row({ index: 0.6, index_low: 0.45, index_high: 0.79 }),
      percentiles
    ),
    ['healthy']
  )
})

test('a null index yields neither verdict', () => {
  assert.deepEqual(failEquipmentSignals(row(), percentiles), [])
})

test('narrow coverage is judged on the percentile tail with an inclusive bound', () => {
  // p10 은 nearest-rank 라 언제나 실제 표본값 하나입니다. 엄격 부등호를 쓰면
  // 그 경계를 정의하는 장비 자신이 자기 꼬리에서 빠집니다.
  assert.deepEqual(
    failEquipmentSignals(
      row({ recipe_count: 4, top_recipe_share: 0.5 }),
      percentiles
    ),
    ['narrow']
  )
  assert.deepEqual(
    failEquipmentSignals(
      row({ recipe_count: 5, top_recipe_share: 0.9 }),
      percentiles
    ),
    []
  )
})

test('no percentiles means no coverage verdict', () => {
  assert.deepEqual(
    failEquipmentSignals(row({ recipe_count: 1, top_recipe_share: 1 }), {}),
    []
  )
})

test('a tool can be both weak and narrow', () => {
  assert.deepEqual(
    failEquipmentSignals(
      row({
        index: 1.8, index_low: 1.52, index_high: 2.11,
        recipe_count: 4, top_recipe_share: 0.7
      }),
      percentiles
    ),
    ['weak', 'narrow']
  )
})

test('isIndexConclusive is false exactly when the interval straddles 1.0', () => {
  assert.equal(isIndexConclusive(row({ index: 1.8, index_low: 1.52, index_high: 2.11 })), true)
  assert.equal(isIndexConclusive(row({ index: 0.6, index_low: 0.45, index_high: 0.79 })), true)
  assert.equal(isIndexConclusive(row({ index: 1.2, index_low: 0.9, index_high: 1.6 })), false)
  assert.equal(isIndexConclusive(row()), false)
})

test('the ceiling and floor sit either side of 1.0', () => {
  // 이 둘이 뒤집히면 모든 장비가 두 배지를 동시에 받습니다.
  assert.ok(FAIL_INDEX_FLOOR < 1 && FAIL_INDEX_CEIL > 1)
})
