// Lot 상세 팝업 recipe 목록의 정렬.
// Run: node --test app/utils/recipeStepSort.test.ts
//
// 이 파일이 존재하는 이유가 곧 이 기능의 검증 방법입니다 — 집의 mock 은
// recipe_id 에 pool index 를 박아 두어(`RCP-{lot}-{idx:03d}`, oper_seq = idx+1)
// 공정순과 이름순이 **항상 같은 결과**를 냅니다. 두 정렬이 실제로 다르다는 것은
// 브라우저로는 집에서 확인할 수 없고, 여기서만 확인됩니다.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { byOperSeq, byRecipeId, sortSteps, stepComparator } from './recipeStepSort.ts'

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

test('이름순은 oper_seq 를 무시한다 — 사무실에서 두 정렬이 갈리는 지점', () => {
  // 사무실 recipe_id 는 MMDM 이 부여한 이름이라 공정 순서와 무관합니다.
  // mock 으로는 절대 만들어지지 않는 배치입니다.
  const rows = [step('AAA_CD', 90), step('ZZZ_CD', 10), step('MMM_CD', 50)]
  assert.deepEqual(ids(sortSteps(rows, 'recipe')), ['AAA_CD', 'MMM_CD', 'ZZZ_CD'])
  assert.deepEqual(ids(sortSteps(rows, 'oper')), ['ZZZ_CD', 'MMM_CD', 'AAA_CD'])
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
