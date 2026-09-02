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

/** 정체성에 쓰는 field. 정렬과 달리 recipe 이름이 아니라 lot 이 필요합니다. */
type IdentifiableStep = Pick<RecipeInfoRow, 'lot_cd' | 'oper_seq' | 'samp_seq'>

/**
 * 목록 한 줄의 정체성 — `v-for` 의 `:key` 로 쓰는 값입니다. 백엔드의 짝은
 * `back_dev_home/ebeam/device_statistics/contracts.py` 의 `step_key` 입니다.
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
 * recipe_id 는 키에 **넣지 않습니다.** 넣어도 유일성은 그대로지만, M 계열 경로는
 * 스텝 이름마다 *최신* recipe_id 를 붙이므로 같은 스텝의 recipe_id 가 조회 시점에
 * 따라 바뀔 수 있습니다 — 그러면 정체성이 그대로인 카드를 Vue 가 버리고 다시
 * 만듭니다. 안정된 키가 하려는 일의 정반대입니다.
 *
 * lot_cd 가 앞에 있는 것은 이 함수가 **호출 범위를 가정하지 않게** 하기 위해서
 * 입니다. 지금 부르는 곳은 한 lot 의 목록뿐이지만, 여러 lot 을 한 목록에 담는
 * 화면이 생겨도 이 키는 그대로 맞습니다.
 */
export const recipeStepKey = (step: IdentifiableStep): string =>
  `${step.lot_cd}/${step.oper_seq}/${step.samp_seq}`

/** 스텝 축 — R3 문서의 정체성 순서 그대로입니다. */
const byStepSeq = (a: SortableStep, b: SortableStep): number =>
  a.oper_seq - b.oper_seq || a.samp_seq - b.samp_seq

/** 이름 축 — MMDM 이 부여한 recipe 이름. 공정 순서와 무관합니다. */
const byName = (a: SortableStep, b: SortableStep): number =>
  a.recipe_id.localeCompare(b.recipe_id)

/**
 * 공정순. 두 축을 **스텝 -> 이름** 순으로 봅니다.
 *
 * M 계열은 원천에 순서 field 가 없어 oper_seq 자체가 공정 접두사 rank 로 합성된
 * 값입니다 (back_dev_home/.../oper_order.py). 그래서 화면에 "실제 운영 공정
 * 순서를 반영하지 않는다" 는 주석이 함께 붙습니다.
 */
export const byOperSeq = (a: SortableStep, b: SortableStep): number =>
  byStepSeq(a, b) || byName(a, b)

/**
 * recipe 이름순. 같은 두 축을 **반대 순서**로 봅니다.
 *
 * 뒤의 스텝 축이 장식이 아닌 이유는 같은 recipe 를 쓰는 스텝이 여럿이기 때문입니다
 * (`recipeStepKey` 주석). 동률 키가 없던 동안 이 정렬은 입력 순서에만 기대고
 * 있었고, 그 순서는 버킷을 바꾸거나 API 를 다시 받으면 달라질 수 있는 값입니다 —
 * 내보내기를 두 번 받아 나란히 비교할 수 없게 됩니다.
 */
export const byRecipeId = (a: SortableStep, b: SortableStep): number =>
  byName(a, b) || byStepSeq(a, b)

/** 정렬 키에 해당하는 비교 함수. */
export const stepComparator = (key: RecipeSortKey) =>
  key === 'recipe' ? byRecipeId : byOperSeq

/** 원본을 건드리지 않고 정렬된 사본을 돌려줍니다. */
export const sortSteps = <T extends SortableStep>(steps: T[], key: RecipeSortKey): T[] =>
  [...steps].sort(stepComparator(key))
