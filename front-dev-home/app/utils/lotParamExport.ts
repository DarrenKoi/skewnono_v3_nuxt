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
import type { RecipeInput } from './ruleEngine'
import type { LotVerdict } from './lotHealth'
import { isExemptJob } from './lotHealth.ts'
import { safeFileNamePart } from './csvDownload.ts'
import { NO_JUDGEMENT, NO_PARAMS, capCell, overCell, paramNoteCell, recipeVerdictCell } from './violationCells.ts'

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
 * 판정이 아예 없는 행의 사유. 세 경우를 **구별해서** 적습니다.
 *
 * 하나로 뭉개면 "이 fab 에는 룰이 없다"(고쳐야 할 일)와 "이 job 은 원래 판정
 * 대상이 아니다"(정상)가 파일에서 같은 말이 됩니다. 특수 job 이 판정 범위
 * 밖인 이유는 `lotHealth.isExemptJob` 에 적혀 있습니다.
 *
 * 나머지 전부는 `violationCells.NO_JUDGEMENT`('판정 결과 없음')입니다 — 룰도
 * 있고 특수 job 도 아닌데 판정에 없는 행. 이 화면에서 그런 행은 **두 표면이
 * 어긋날 때** 나옵니다: recipe 목록은 recipe-statistics 에서 오고 판정은
 * recipe-params 에서 오므로, 버킷에는 있는데 recipe-params 에 행이 없는 recipe
 * 가 그렇습니다. 왜인지는 여기서 알 수 없으니 아는 만큼만 적습니다 — 모르는
 * 것을 '룰 없음' 이라고 적으면 있지도 않은 원인을 파일이 지목하게 됩니다.
 */
const NO_VERDICT = {
  exempt: '판정 범위 밖(특수 job)',
  noRules: '룰 없음'
} as const

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
 * `verdict` 는 이 lot 의 판정(`buildLotVerdicts` 의 산물)입니다. 판정 결과
 * 배열이 아니라 verdict 를 통째로 받는 것은, 룰이 없다는 사실을 **verdict 가
 * 스스로 말하기** 때문입니다(`kind: 'no-rules'`). 배열만 받으면 그 사실이
 * 배열의 비어 있음으로 표현되고, 빈 배열은 타입이 잡아 주지 못하는 합법적인
 * 값이라 넘기기를 잊은 날 파일이 모든 행을 '룰 없음' 이라고 잘못 소개합니다.
 */
export const buildLotParamRows = (
  orderedRecipes: RecipeInfoRow[],
  recipeParams: RecipeInput[],
  verdict: LotVerdict | undefined
): string[][] => {
  const paramsByRecipe = new Map<string, RecipeInput>()
  for (const recipe of recipeParams) paramsByRecipe.set(recipe.recipe_id, recipe)

  const resultByRecipe = new Map((verdict?.recipes ?? []).map(r => [r.recipe_id, r]))
  // `kind` 하나로는 룰이 없다고 단정할 수 없습니다. `buildLotVerdicts` 는 판정한
  // recipe 가 0 건이면 **룰이 있어도** 'no-rules' 를 답니다(d6e6aacb) — 전 recipe
  // 가 gray 인 lot 이 그렇습니다. 그때 gray 가 남아 있다는 것이 곧 "룰은 있었다"
  // 는 증거이고, 같은 화면의 LotTable 툴팁이 이미 그 기준으로 원인을 가릅니다.
  const noRules = (verdict?.kind ?? 'no-rules') === 'no-rules'
    && (verdict?.gray_recipes ?? 0) === 0

  const rows: string[][] = []
  for (const recipe of orderedRecipes) {
    const parameters = paramsByRecipe.get(recipe.recipe_id)?.parameters ?? []
    const result = resultByRecipe.get(recipe.recipe_id)
    // 판정이 없는 recipe 는 왜 없는지가 곧 사유입니다. 판정 범위 밖 job 은
    // `buildLotVerdicts` 가 애초에 판정에 넣지 않으므로 여기서 이름으로
    // 되짚습니다 — 그 판단의 주인은 계속 `isExemptJob` 하나입니다.
    const missing = isExemptJob(recipe.recipe_id)
      ? NO_VERDICT.exempt
      : noRules ? NO_VERDICT.noRules : NO_JUDGEMENT
    const verdictLabel = result ? recipeVerdictCell(result) : missing

    if (parameters.length === 0) {
      rows.push([
        recipe.lot_cd, recipe.oper_desc, recipe.recipe_id, verdictLabel,
        '', '', '', '', result ? NO_PARAMS : missing
      ])
      continue
    }
    const resultByName = new Map((result?.results ?? []).map(r => [r.name, r]))
    for (const param of parameters) {
      // recipe 는 판정됐는데 이 파라미터만 없는 가지입니다. **오늘은 닿지
      // 않습니다** — `scopeRecipesToBucket` 이 파라미터를 한 번만 좁히고 그
      // 결과가 판정과 화면 양쪽에 그대로 가므로 두 배열이 같습니다. 그래도
      // 이름으로 잇고 이 가지를 남기는 것은, 순서로 이으면 한쪽만 좁혀진 날
      // 한 칸씩 밀린 cap 이 **조용히** 붙기 때문입니다. 사유는 recipe 층 사유가
      // 아닙니다 — recipe 는 룰을 찾았으므로 '룰 없음' 은 거짓말이 됩니다.
      const p = result && resultByName.get(param.name)
      rows.push([
        recipe.lot_cd,
        recipe.oper_desc,
        recipe.recipe_id,
        verdictLabel,
        param.name,
        String(param.point_count),
        p ? String(capCell(p)) : '',
        p ? overCell(p) : '',
        p ? paramNoteCell(result, p) : (result ? NO_JUDGEMENT : missing)
      ])
    }
  }
  return rows
}

/**
 * 내보내기 파일 이름.
 *
 * `outlier` 는 화면이 "초과만" 으로 좁혀진 상태에서 받은 파일이라는 표시입니다
 * — 행 수는 파일을 열어야 보이므로 이름이 말합니다. 예전 이름은 `_flagged`
 * 였는데, 이 파일이 `상한 초과` 열을 갖게 된 뒤로는 못 쓰는 이름입니다: 화면의
 * "초과만" 칩은 **중앙값 초과**(이 lot 자신의 중앙값 × 2, 파라미터 단위)로
 * 거르고, 열은 **상한 초과**(룰의 cap, recipe 단위)를 말합니다. 한쪽이 0 이면서
 * 다른 쪽이 클 수 있어서 두 축은 이름으로 갈라 두기로 했습니다(b589fe39).
 * `_flagged` 로는 어느 초과가 행을 골랐는지 알 수 없었습니다.
 *
 * `judgeSons` 는 son 파라미터를 판정에 넣었는지입니다. 이 화면에는 그 토글이
 * **보이지 않는데**(측정 룰 탭의 설정을 usePersistedState 로 함께 씁니다) cap ·
 * 상한 초과 열은 그 값에 딸려 옵니다. 적지 않으면 두 사람이 같은 lot 을 받아
 * 서로 다른 파일을 얻고도 왜인지 알 길이 없습니다 — 워크북 쪽은 요약 시트에
 * 같은 사실을 적습니다.
 *
 * 버킷 키의 "_summary" 꼬리는 뗍니다. 그 꼬리는 API 응답에서 요약 표면을
 * 가리키는 이름인데, 이 파일은 요약이 아니라 그 아래 파라미터 명세입니다 —
 * `R0A8_all_summary_params.csv` 는 파일 이름이 스스로를 잘못 소개하는 꼴입니다.
 *
 * lot 코드는 office 값이라 파일명으로 쓰기 전에 씻어 냅니다 — `safeFileNamePart`.
 */
export const lotParamFileName = (
  lotCd: string,
  bucket: string,
  outlier = false,
  judgeSons = true
): string => {
  const suffix = `${outlier ? '_outlier' : ''}${judgeSons ? '' : '_nosons'}`
  return `${safeFileNamePart(lotCd)}_${safeFileNamePart(bucket.replace(/_summary$/, ''))}_params${suffix}.csv`
}
