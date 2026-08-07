import type { RecipeInfoRow } from '~/composables/useRecipeStatisticsApi'

/**
 * Lot 상세 팝업의 recipe 목록 정렬.
 *
 * 기본은 **공정순(oper_seq)** 입니다. 예전 기본이던 para_all 내림차순은 "어느
 * recipe 가 제일 무거운가" 라는 질문의 순서인데, 이 목록을 여는 질문은 "이
 * device 가 공정을 따라가며 무엇을 재는가" 입니다 — 위에서 아래로 읽는 것이
 * wafer 가 지나가는 순서와 같아야 합니다. para 가 큰 recipe 는 막대 길이로
 * 이미 눈에 띄므로 정렬까지 그 축을 쓸 이유가 없습니다.
 *
 * **집에서는 두 정렬이 같은 결과를 냅니다.** mock 의 recipe_id 가
 * `RCP-{lot}-{idx:03d}` 이고 oper_seq 가 `idx + 1` 이라, 이름순과 공정순이
 * 구조적으로 일치하기 때문입니다 (providers/recipe_population.py `_identity_pool`).
 * 사무실에서는 recipe_id 가 MMDM 이 부여한 실제 이름이라 둘이 갈라집니다 —
 * 그래서 이 파일의 테스트가 두 정렬을 구분하는 유일한 장치입니다. 화면으로는
 * 집에서 절대 확인되지 않습니다.
 */
export type RecipeSortKey = 'oper' | 'recipe'

type SortableStep = Pick<RecipeInfoRow, 'oper_seq' | 'samp_seq' | 'recipe_id'>

/**
 * 공정순. 동률은 samp_seq -> recipe_id 로 갈라집니다.
 *
 * R3 에서 스텝의 정체성은 (oper_seq, samp_seq) 이므로 samp_seq 가 두 번째 키여야
 * 합니다. 마지막 recipe_id 는 **결정론을 위한 것**입니다 — 같은 입력이 항상 같은
 * 순서를 내지 않으면 CSV 를 두 번 받아 나란히 비교할 수 없습니다.
 *
 * M 계열은 원천에 순서 field 가 없어 oper_seq 자체가 공정 접두사 rank 로 합성된
 * 값입니다 (back_dev_home/.../oper_order.py). 그래서 화면에 "실제 운영 공정
 * 순서를 반영하지 않는다" 는 주석이 함께 붙습니다.
 */
export const byOperSeq = (a: SortableStep, b: SortableStep): number =>
  a.oper_seq - b.oper_seq
  || a.samp_seq - b.samp_seq
  || a.recipe_id.localeCompare(b.recipe_id)

/** recipe 이름순. recipe_id 는 lot 안에서 유일하므로 추가 동률 키가 없습니다. */
export const byRecipeId = (a: SortableStep, b: SortableStep): number =>
  a.recipe_id.localeCompare(b.recipe_id)

/** 정렬 키에 해당하는 비교 함수. */
export const stepComparator = (key: RecipeSortKey) =>
  key === 'recipe' ? byRecipeId : byOperSeq

/** 원본을 건드리지 않고 정렬된 사본을 돌려줍니다. */
export const sortSteps = <T extends SortableStep>(steps: T[], key: RecipeSortKey): T[] =>
  [...steps].sort(stepComparator(key))
