// 한 lot 의 "스텝 → recipe → 파라미터" 를 한 장의 표로 펴는 빌더.
//
// 화면은 이 정보를 세 곳에 나눠 들고 있습니다 — 스텝 이름(oper_desc)은 요약
// 표면(recipe-statistics)에, 파라미터와 측정 point 수는 recipe-params 에,
// 상한 판정은 `buildLotVerdicts` 가 만든 lot verdict 에 있습니다. 엔지니어가
// 엑셀에서 보고 싶어 하는 것은 그 셋을 이어 붙인 **파라미터 한 줄짜리** 표라,
// 여기서 recipe_id 로 조인합니다. recipe_id 로 이을 수 있는 것은 그것이 세
// 표면을 가로지르는 조인 키이기 때문입니다 (docs/datatables/hitachi/idp_ver.txt L55).
//
// 판정은 여기서 하지 않고 **받습니다**. 화면(lot 요약 표의 상한 초과 열)과 이
// 파일이 같은 lot 에 다른 숫자를 말할 자리를 만들지 않기 위해서입니다 — 같은
// 이유로 모달도 recipeParams 를 스스로 좁히지 않습니다.
//
// 순수 함수라 `node --test` 가 그대로 실행합니다 — 컴포넌트 안에 두면
// 테스트가 볼 수 없습니다.
import type { RecipeInfoRow } from '~/composables/useRecipeStatisticsApi'
import type { RecipeInput, RecipeResult } from './ruleEngine'
import { isExemptJob } from './lotHealth.ts'
import { capCell, overCell, paramNoteCell, recipeVerdictCell } from './violationCells.ts'

/** 엑셀 첫 줄. 화면 용어와 같은 말을 씁니다. */
export const LOT_PARAM_HEADERS = [
  'lot_cd',
  'step',
  'recipe_id',
  'recipe_판정',
  'parameter',
  'measure_points',
  'cap',
  '상한 초과',
  '비고'
] as const

/**
 * 판정이 아예 없는 recipe 의 사유. 두 경우를 **구별해서** 적습니다.
 *
 * 하나로 뭉개면 "이 fab 에는 룰이 없다" 와 "이 job 은 원래 판정 대상이
 * 아니다" 가 파일에서 같은 말이 되고, 앞의 것은 고쳐야 할 일이지만 뒤의 것은
 * 정상입니다. 특수 job 이 판정 범위 밖인 이유는 `lotHealth.isExemptJob` 에
 * 적혀 있습니다.
 */
const NO_VERDICT = { exempt: '판정 범위 밖(특수 job)', noRules: '룰 없음' } as const

/**
 * recipe 순서는 **호출자가 정해서 넘깁니다** — 화면에 보이는 순서 그대로
 * 내보내기 위해서입니다. 파라미터 순서는 여기서 절대 건드리지 않습니다:
 * 원본 순서가 곧 정보이고(WAFER 계열이 맨 앞), 이름순으로 정렬하면 가장 중요한
 * 파라미터가 맨 아래로 밀립니다 (docs/datatables/hitachi/recipe_params.txt).
 *
 * 파라미터가 없는 recipe 도 **한 줄로 남깁니다**. 건너뛰면 그 스텝이 표에서
 * 통째로 사라져, 읽는 사람은 "측정 파라미터가 없는 recipe" 와 "받아오지 못한
 * recipe" 를 구분할 수 없습니다.
 *
 * `verdictRecipes` 는 이 lot 의 판정 결과(`LotVerdict.recipes`)입니다. 기본값을
 * 두지 않은 것은 빈 배열이 곧 "이 fab 에 룰이 없다" 를 뜻하기 때문입니다 —
 * 넘기는 것을 잊으면 파일이 모든 행을 '룰 없음' 이라고 잘못 소개합니다.
 */
export const buildLotParamRows = (
  orderedRecipes: RecipeInfoRow[],
  recipeParams: RecipeInput[],
  verdictRecipes: RecipeResult[]
): string[][] => {
  const paramsByRecipe = new Map<string, RecipeInput>()
  for (const recipe of recipeParams) paramsByRecipe.set(recipe.recipe_id, recipe)

  const verdictByRecipe = new Map<string, RecipeResult>()
  for (const result of verdictRecipes) verdictByRecipe.set(result.recipe_id, result)

  const rows: string[][] = []
  for (const recipe of orderedRecipes) {
    const parameters = paramsByRecipe.get(recipe.recipe_id)?.parameters ?? []
    const verdict = verdictByRecipe.get(recipe.recipe_id)
    // 판정이 없는 recipe 는 왜 없는지가 곧 사유입니다. 판정 범위 밖 job 은
    // `buildLotVerdicts` 가 애초에 판정에 넣지 않으므로 여기서 이름으로
    // 되짚습니다 — 그 판단의 주인은 계속 `isExemptJob` 하나입니다.
    const missing = isExemptJob(recipe.recipe_id) ? NO_VERDICT.exempt : NO_VERDICT.noRules
    const verdictLabel = recipeVerdictCell(verdict, missing)

    if (parameters.length === 0) {
      rows.push([
        recipe.lot_cd, recipe.oper_desc, recipe.recipe_id, verdictLabel,
        '', '', '', '', verdict ? '' : missing
      ])
      continue
    }
    // 파라미터 판정은 이름으로 잇습니다. 순서로 이으면 mother 버킷처럼 한쪽만
    // 좁혀진 날 한 칸씩 밀린 cap 이 조용히 붙습니다.
    const resultByName = new Map((verdict?.results ?? []).map(r => [r.name, r]))
    for (const param of parameters) {
      const result = resultByName.get(param.name)
      rows.push([
        recipe.lot_cd,
        recipe.oper_desc,
        recipe.recipe_id,
        verdictLabel,
        param.name,
        String(param.point_count),
        String(capCell(result)),
        overCell(result),
        paramNoteCell(verdict, result, missing)
      ])
    }
  }
  return rows
}

/**
 * 내보내기 파일 이름. `flagged` 는 화면이 초과만 보여 주는 상태에서 받은
 * 파일이라는 표시입니다 — 행 수는 파일을 열어야 보이므로 이름이 말합니다.
 *
 * 버킷 키의 "_summary" 꼬리는 뗍니다. 그 꼬리는 API 응답에서 요약 표면을
 * 가리키는 이름인데, 이 파일은 요약이 아니라 그 아래 파라미터 명세입니다 —
 * `R0A8_all_summary_params.csv` 는 파일 이름이 스스로를 잘못 소개하는 꼴입니다.
 *
 * lot 코드는 office 값이라 파일명으로 쓰기 전에 씻어 냅니다
 * (recipeParamExport.paramExportFilename 과 같은 이유).
 */
export const lotParamFileName = (lotCd: string, bucket: string, flagged = false): string => {
  const safe = (value: string) => (value || 'unknown').replace(/[^\w.-]+/g, '_')
  const suffix = flagged ? '_flagged' : ''
  return `${safe(lotCd)}_${safe(bucket.replace(/_summary$/, ''))}_params${suffix}.csv`
}
