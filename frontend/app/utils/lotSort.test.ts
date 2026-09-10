// 비교 페이지 "정렬" 칩의 어휘.
// Run: node --test app/utils/lotSort.test.ts
//
// 여기서 지키는 것은 **한 칩이 두 표면을 같은 순서로 만든다**는 규칙입니다 —
// 막대 차트는 sortLots 로 배열을 정렬하고, Lot 요약 표는 LOT_SORT 의 `column`
// 이 가리키는 열로 정렬합니다. 둘이 갈라지는 자리는 동률과 열 id 두 곳이고,
// 열 id 가 실재하는지는 LotTable 이 타입으로 확인하므로(chipSorting) 여기서는
// 동률과 대응 자체를 겨냥합니다.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { LOT_SORT, sortLots } from './lotSort.ts'
import { paraTotal } from './lotHealth.ts'

const lot = (lot_cd: string, para_5: number, avail_recipe: number) =>
  ({ lot_cd, para_5, para_9: 0, para_13: 0, para_16: 0, para_over_16: 0, avail_recipe })

const ids = (rows: { lot_cd: string }[]) => rows.map(r => r.lot_cd)

test('이름순은 lot_cd 오름차순이다', () => {
  const rows = [lot('C', 9, 1), lot('A', 1, 9), lot('B', 5, 5)]
  assert.deepEqual(ids(sortLots(rows, 'default')), ['A', 'B', 'C'])
})

test('파라미터·운용 recipe 는 내림차순이다 — 많은 쪽이 볼 일입니다', () => {
  const rows = [lot('small', 3, 3), lot('big', 30, 1), lot('mid', 10, 20)]
  assert.deepEqual(ids(sortLots(rows, 'paraStack')), ['big', 'mid', 'small'])
  assert.deepEqual(ids(sortLots(rows, 'availRecipe')), ['mid', 'small', 'big'])
})

test('값 동률은 lot 이름으로 갈린다 — 차트와 표가 어긋나지 않으려면', () => {
  // 표(TanStack)는 자기 행 모델을 정렬하고 차트는 요약 배열을 정렬하므로, 동률을
  // 입력 순서에 맡기면 같은 칩에서 위아래 순서가 달라질 수 있습니다.
  const rows = [lot('B', 7, 4), lot('A', 7, 4)]
  assert.deepEqual(ids(sortLots(rows, 'paraStack')), ['A', 'B'])
  assert.deepEqual(ids(sortLots([...rows].reverse(), 'paraStack')), ['A', 'B'])
  assert.deepEqual(ids(sortLots(rows, 'availRecipe')), ['A', 'B'])
})

test('원본 배열을 건드리지 않는다', () => {
  const rows = [lot('C', 1, 1), lot('A', 2, 2)]
  sortLots(rows, 'default')
  assert.deepEqual(ids(rows), ['C', 'A'])
})

test('파라미터 정렬은 다섯 구간 합을 본다 — para_5 하나가 아니라', () => {
  // paraTotal 이 축이므로 큰 구간에만 값이 있는 lot 이 앞에 서야 합니다.
  const wide = { ...lot('wide', 0, 1), para_16: 40 }
  const narrow = lot('narrow', 20, 1)
  assert.equal(paraTotal(wide), 40)
  assert.deepEqual(ids(sortLots([narrow, wide], 'paraStack')), ['wide', 'narrow'])
})

test('세 칩이 모두 표의 열을 하나씩 가리킨다', () => {
  // 정렬 방향은 여기 적힌 desc 하나에서 나옵니다(비교 함수도 이것을 읽습니다).
  // 이 표가 고정하는 것은 **어느 열이냐** 입니다 — 열 이름이 조용히 바뀌면
  // 칩만 눌리고 표는 그대로가 됩니다. 그 열이 실재하는지는 LotTable 의
  // chipSorting 이 타입으로 확인합니다.
  assert.deepEqual(
    Object.fromEntries(Object.entries(LOT_SORT).map(([key, spec]) => [key, spec.column])),
    { default: 'lot_cd', paraStack: 'para_total', availRecipe: 'avail_recipe' }
  )
})
