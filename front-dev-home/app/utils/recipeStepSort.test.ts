// Lot 상세 팝업 recipe 목록의 정렬.
// Run: node --test app/utils/recipeStepSort.test.ts
//
// 여기서 지키는 것은 **비교 함수의 규칙**입니다 — 동률을 가르는 순서, 결정론,
// 입력 불변성. 두 정렬이 실제로 다른 표를 낸다는 사실은 mock 쪽 회귀 테스트가
// 지킵니다 (back_dev_home/.../test_recipe_population.py
// test_recipe_name_order_differs_from_process_order).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { byOperSeq, byRecipeId, sortSteps, stepComparator, stepKey } from './recipeStepSort.ts'

const step = (recipe_id: string, oper_seq: number, samp_seq = 1) =>
  ({ recipe_id, oper_seq, samp_seq })

const ids = (rows: { recipe_id: string }[]) => rows.map(r => r.recipe_id)

test('공정순은 oper_seq 오름차순이다', () => {
  const rows = [step('C', 30), step('A', 10), step('B', 20)]
  assert.deepEqual(ids(sortSteps(rows, 'oper')), ['A', 'B', 'C'])
})

test('oper_seq 동률은 samp_seq 로 갈린다 — R3 의 스텝 정체성이 (oper_seq, samp_seq) 이므로', () => {
  const rows = [step('third', 7, 5), step('first', 7, 1), step('second', 7, 3)]
  assert.deepEqual(ids(sortSteps(rows, 'oper')), ['first', 'second', 'third'])
})

test('oper_seq·samp_seq 가 모두 같으면 recipe_id 로 갈려 순서가 결정론적이다', () => {
  // 같은 입력이 항상 같은 순서를 내지 않으면 CSV 를 두 번 받아 비교할 수 없습니다.
  const rows = [step('RCP-B', 4, 2), step('RCP-A', 4, 2)]
  assert.deepEqual(ids(sortSteps(rows, 'oper')), ['RCP-A', 'RCP-B'])
  assert.deepEqual(ids(sortSteps([...rows].reverse(), 'oper')), ['RCP-A', 'RCP-B'])
})

test('이름순은 oper_seq 를 무시한다 — 두 정렬이 갈리는 지점', () => {
  // 사무실 recipe_id 는 MMDM 이 부여한 이름이라 공정 순서와 무관합니다.
  // mock 으로는 절대 만들어지지 않는 배치입니다.
  const rows = [step('AAA_CD', 90), step('ZZZ_CD', 10), step('MMM_CD', 50)]
  assert.deepEqual(ids(sortSteps(rows, 'recipe')), ['AAA_CD', 'MMM_CD', 'ZZZ_CD'])
  assert.deepEqual(ids(sortSteps(rows, 'oper')), ['ZZZ_CD', 'MMM_CD', 'AAA_CD'])
})

test('이름순 동률은 oper_seq -> samp_seq 로 갈린다 — 같은 recipe 를 여러 스텝이 쓰므로', () => {
  // 한 device 가 같은 측정 recipe 를 여러 공정에서 돌립니다. 동률 키가 없으면 이
  // 정렬은 입력 순서에만 기대고, 그 순서는 버킷을 바꾸면 달라질 수 있습니다.
  const rows = [step('ADI/LINE_CD', 46, 5), step('ADI/LINE_CD', 4, 2), step('ADI/LINE_CD', 4, 1)]
  const sorted = sortSteps(rows, 'recipe')
  assert.deepEqual(sorted.map(r => [r.oper_seq, r.samp_seq]), [[4, 1], [4, 2], [46, 5]])
  assert.deepEqual(sortSteps([...rows].reverse(), 'recipe'), sorted)
})

test('stepKey 는 같은 recipe 를 쓰는 두 스텝을 갈라낸다 — v-for :key 의 계약', () => {
  // recipe_id 를 :key 로 쓰면 Vue 가 두 카드를 하나로 접어 스텝이 사라집니다
  // ("Duplicate keys found during update"). 사무실 데이터에서 실제로 났습니다.
  const shared = [step('ADI/LINE_CD', 4, 2), step('ADI/LINE_CD', 46, 5)]
  const keys = shared.map(stepKey)

  assert.equal(new Set(keys).size, 2)
  assert.equal(new Set(shared.map(r => r.recipe_id)).size, 1)
})

test('stepKey 는 samp_seq 만 다른 스텝도 갈라낸다', () => {
  // R3 문서 1건이 (prod_id, oper_seq, samp_seq) 이므로 samp_seq 가 키에 있어야
  // 같은 공정의 sample 측정 두 건이 한 장으로 접히지 않습니다.
  assert.notEqual(stepKey(step('ADI/LINE_CD', 4, 1)), stepKey(step('ADI/LINE_CD', 4, 2)))
})

test('stepComparator 는 키에 맞는 비교 함수를 준다', () => {
  assert.equal(stepComparator('oper'), byOperSeq)
  assert.equal(stepComparator('recipe'), byRecipeId)
})

test('sortSteps 는 입력 배열을 건드리지 않는다', () => {
  // 화면의 lotRecipes 는 computed 가 돌려주는 배열이라, 제자리 정렬하면
  // 다른 소비처(CSV 빌더)가 보는 순서까지 조용히 바뀝니다.
  const rows = [step('B', 2), step('A', 1)]
  sortSteps(rows, 'oper')
  assert.deepEqual(ids(rows), ['B', 'A'])
})
