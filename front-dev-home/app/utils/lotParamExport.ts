// 한 lot 의 "스텝 → recipe → 파라미터" 를 한 장의 표로 펴는 빌더.
//
// 화면은 이 정보를 두 곳에 나눠 들고 있습니다 — 스텝 이름(oper_desc)은 요약
// 표면(recipe-statistics)에, 파라미터와 측정 point 수는 recipe-params 에
// 있습니다. 엔지니어가 엑셀에서 보고 싶어 하는 것은 그 둘을 이어 붙인
// **파라미터 한 줄짜리** 표라, 여기서 recipe_id 로 조인합니다. recipe_id 로
// 이을 수 있는 것은 그것이 두 DB 를 가로지르는 조인 키이기 때문입니다
// (docs/datatables/idp_ver.txt L55).
//
// 순수 함수라 `node --test` 가 그대로 실행합니다 — 컴포넌트 안에 두면
// 테스트가 볼 수 없습니다. 값 import 가 없으므로 타입만 가져옵니다.
import type { RecipeInfoRow } from '~/composables/useRecipeStatisticsApi'
import type { RecipeInput } from './ruleEngine'

/** 엑셀 첫 줄. 화면 용어와 같은 말을 씁니다. */
export const LOT_PARAM_HEADERS = [
  'lot_cd',
  'step',
  'recipe_id',
  'parameter',
  'measure_points'
] as const

/**
 * recipe 순서는 **호출자가 정해서 넘깁니다** — 화면에 보이는 순서 그대로
 * 내보내기 위해서입니다. 파라미터 순서는 여기서 절대 건드리지 않습니다:
 * 원본 순서가 곧 정보이고(WAFER 계열이 맨 앞), 이름순으로 정렬하면 가장 중요한
 * 파라미터가 맨 아래로 밀립니다 (docs/datatables/recipe_params.txt).
 *
 * 파라미터가 없는 recipe 도 **한 줄로 남깁니다**. 건너뛰면 그 스텝이 표에서
 * 통째로 사라져, 읽는 사람은 "측정 파라미터가 없는 recipe" 와 "받아오지 못한
 * recipe" 를 구분할 수 없습니다.
 */
export const buildLotParamRows = (
  orderedRecipes: RecipeInfoRow[],
  recipeParams: RecipeInput[]
): string[][] => {
  const paramsByRecipe = new Map<string, RecipeInput>()
  for (const recipe of recipeParams) paramsByRecipe.set(recipe.recipe_id, recipe)

  const rows: string[][] = []
  for (const recipe of orderedRecipes) {
    const parameters = paramsByRecipe.get(recipe.recipe_id)?.parameters ?? []
    if (parameters.length === 0) {
      rows.push([recipe.lot_cd, recipe.oper_desc, recipe.recipe_id, '', ''])
      continue
    }
    for (const param of parameters) {
      rows.push([
        recipe.lot_cd,
        recipe.oper_desc,
        recipe.recipe_id,
        param.name,
        String(param.point_count)
      ])
    }
  }
  return rows
}

/**
 * `R0A8_only_normal_params.csv`.
 *
 * 버킷 키의 "_summary" 꼬리는 뗍니다. 그 꼬리는 API 응답에서 요약 표면을
 * 가리키는 이름인데, 이 파일은 요약이 아니라 그 아래 파라미터 명세입니다 —
 * `R0A8_all_summary_params.csv` 는 파일 이름이 스스로를 잘못 소개하는 꼴입니다.
 *
 * lot 코드는 office 값이라 파일명으로 쓰기 전에 씻어 냅니다
 * (recipeParamExport.paramExportFilename 과 같은 이유).
 */
export const lotParamFileName = (lotCd: string, bucket: string): string => {
  const safe = (value: string) => (value || 'unknown').replace(/[^\w.-]+/g, '_')
  return `${safe(lotCd)}_${safe(bucket.replace(/_summary$/, ''))}_params.csv`
}
