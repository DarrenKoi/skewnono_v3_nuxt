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
 * 두 정렬은 **집에서도 다른 결과를 냅니다.** recipe_id 는 사무실에서 MMDM 이
 * 부여한 `class_name/recipe_name` 이라 공정 순서와 무관한 축인데, mock 도 그
 * 독립성을 재현하기 때문입니다 — class 를 lot·idx digest 로 고릅니다
 * (providers/recipe_population.py `_recipe_name`). 예전 mock 의
 * `RCP-{lot}-{idx:03d}` 는 oper_seq 가 `idx + 1` 이라 두 축이 완전상관이었고,
 * 정렬 칩을 눌러도 같은 표가 다시 그려졌습니다.
 */
export type RecipeSortKey = 'oper' | 'recipe'

type SortableStep = Pick<RecipeInfoRow, 'oper_seq' | 'samp_seq' | 'recipe_id'>

/**
 * 목록 한 줄의 정체성 — `v-for` 의 `:key` 로 쓰는 값입니다.
 *
 * **recipe_id 가 아닙니다.** 한 device 는 같은 측정 recipe 를 여러 공정에서
 * 돌리므로 recipe_id 는 lot 안에서 반복됩니다. R3 는 문서 1건이
 * `(prod_id, oper_seq, samp_seq)` 이고, M 계열은 스텝 이름마다 최신 recipe_id 를
 * 붙이는 집계라 한 recipe 가 두 스텝에 걸립니다
 * (back_dev_home/.../office_example.py `_r3_steps` / `_mfab_steps`).
 *
 * recipe_id 를 키로 쓰던 동안 Vue 가 두 카드를 하나로 접어 **스텝이 조용히
 * 사라졌습니다** ("Duplicate keys found during update"). 집의 mock 이 그때
 * recipe_id 를 lot 안에서 유일하게 만들고 있어 이 경로가 한 번도 재현되지
 * 않았습니다 — 지금은 재현합니다
 * (providers/recipe_population.py `_apply_shared_recipes`).
 *
 * 뒤에 recipe_id 를 붙여 두는 것은 devtools 에서 키를 사람이 읽기 위해서입니다.
 * 앞의 두 값만으로 이미 유일합니다.
 */
export const stepKey = (step: SortableStep): string =>
  `${step.oper_seq}/${step.samp_seq}/${step.recipe_id}`

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

/**
 * recipe 이름순. 동률은 oper_seq -> samp_seq 로 갈라집니다.
 *
 * 같은 recipe 를 쓰는 스텝이 여럿이라 **동률이 실제로 생깁니다** (`stepKey` 주석).
 * 동률 키가 없던 동안 이 정렬은 입력 순서에만 기대고 있었고, 그 순서는 버킷을
 * 바꾸거나 API 를 다시 받으면 달라질 수 있는 값입니다 — CSV 를 두 번 받아 나란히
 * 비교할 수 없게 됩니다.
 */
export const byRecipeId = (a: SortableStep, b: SortableStep): number =>
  a.recipe_id.localeCompare(b.recipe_id)
  || a.oper_seq - b.oper_seq
  || a.samp_seq - b.samp_seq

/** 정렬 키에 해당하는 비교 함수. */
export const stepComparator = (key: RecipeSortKey) =>
  key === 'recipe' ? byRecipeId : byOperSeq

/** 원본을 건드리지 않고 정렬된 사본을 돌려줍니다. */
export const sortSteps = <T extends SortableStep>(steps: T[], key: RecipeSortKey): T[] =>
  [...steps].sort(stepComparator(key))
