/**
 * "R3 룰 준수" 표의 한 디바이스를 워크북으로.
 *
 * 자세히(DrillSlideover)와 **같은 판정**을 담습니다. 같은 판정이라는 것이
 * 문구가 아니라 구조여야 해서, 화면이 그리는 `DrillDevice` 가 아니라 그 위쪽의
 * `LotHealth` 를 받습니다 — 화면은 그것을 `toViolationDrill` 로 접어 그리고,
 * 여기는 같은 것을 그대로 폅니다. `DrillDevice` 를 받으면 cap 이 `cap 10`
 * 이라는 꼬리표 문자열로 이미 타 버린 뒤라, 엑셀에 숫자로 넣으려면 그 문자열을
 * 도로 뜯어야 합니다.
 *
 * 파일을 쓰지 않는 순수 함수입니다. 쓰는 쪽은 `./xlsx.ts` 이고, 그 분리선이
 * 곧 `node --test` 로 검증할 수 있는 범위의 경계입니다.
 */
import type { LotHealth } from './ruleEngine.ts'
import type { WorkbookSheet } from './xlsx.ts'
import { safeFileNamePart } from './csvDownload.ts'
import { NO_PARAMS, ROLE_HEADER, capCell, overCell, paramNoteCell, recipeVerdictCell, roleCell } from './violationCells.ts'

/**
 * 엑셀 첫 줄. 판정은 recipe 층과 파라미터 층 **양쪽**에 답니다 —
 * 스프레드시트에는 슬라이드오버의 접힘/펼침이 없어서, recipe 층 판정을
 * 파라미터 행에서 그룹으로 되짚어야 하면 자동 필터 한 번에 답이 안 나옵니다.
 */
export const COMPLIANCE_HEADERS = [
  'lot_cd',
  'recipe_id',
  'recipe_판정',
  'parameter',
  ROLE_HEADER,
  'measure_points',
  'cap',
  '상한 초과',
  '비고'
] as const

export interface ComplianceExportInput {
  /** 표가 이미 판정한 결과 그대로. 여기서 다시 판정하지 않습니다. */
  health: LotHealth
  /**
   * 판정 범위 밖이라 `health` 에 들어가지도 않은 특수 job 건수.
   *
   * 요약이 이 수를 적지 않으면 파일과 화면을 맞출 수 없습니다 — 표의 `recipe`
   * 열은 특수 job 을 **포함한** 전체를 보여 주는데(그 열의 주석이 "사라진 것이
   * 없음을 보입니다" 라고 적어 둔 이유입니다) 요약의 `판정 범위 recipe` 는
   * 걷어낸 뒤의 수라, 둘을 나란히 놓으면 차이가 설명 없이 남습니다. 같은 lot 에
   * 두 숫자가 이유 없이 다르게 보이던 것이 b589fe39 가 고친 일입니다.
   */
  exempt: number
  /** 표 위 토글. 파일의 숫자가 이 값에 딸려 오므로 요약에 적습니다. */
  judgeSons: boolean
  exportedAt: string
}

/**
 * 파라미터 한 줄짜리 표. recipe 순서도 파라미터 순서도 건드리지 않습니다 —
 * `health.recipes` 와 `results` 의 순서가 곧 자세히가 그리는 순서입니다.
 *
 * 파라미터가 없는 recipe 도 한 줄로 남깁니다. 건너뛰면 그 recipe 가 파일에서
 * 통째로 사라져, "측정 파라미터가 없는 recipe" 와 "받아오지 못한 recipe" 를
 * 구분할 수 없습니다 (lotParamExport 와 같은 결정, 같은 말).
 *
 * 판정이 없는 recipe 는 여기 올 수 없습니다 — 이 표는 룰이 있는 R3 만 다루고,
 * 판정 범위 밖 job 은 화면이 `evaluateLot` 에 넘기기 전에 이미 걸렀습니다.
 */
const judgementRows = (health: LotHealth): (string | number)[][] => {
  const rows: (string | number)[][] = [[...COMPLIANCE_HEADERS]]
  for (const recipe of health.recipes) {
    const verdict = recipeVerdictCell(recipe)
    if (recipe.results.length === 0) {
      rows.push([health.lot_cd, recipe.recipe_id, verdict, '', '', '', '', '', NO_PARAMS])
      continue
    }
    for (const param of recipe.results) {
      rows.push([
        health.lot_cd,
        recipe.recipe_id,
        verdict,
        param.name,
        roleCell(param.role),
        param.point_count,
        capCell(param),
        overCell(param),
        paramNoteCell(recipe, param)
      ])
    }
  }
  return rows
}

/**
 * 슬라이드오버 머리말의 세 숫자(recipe · 상한 초과 recipe · 상한 초과 파라미터)에
 * 화면에서는 옆에 있지만 파일에는 따라오지 않는 것들을 더합니다.
 *
 *   판정 recipe — 표의 배지가 `초과 / 판정` 으로 쓰는 분모입니다. 이것이 없으면
 *     "상한 초과 60" 이 몇 건 중 60 인지 파일만 봐서는 알 수 없습니다.
 *   특수 job — 판정 범위 밖이라 위 어느 수에도 들어가지 않은 recipe. 표의
 *     `recipe` 열과 요약의 `판정 범위 recipe` 가 다른 이유가 이 줄입니다.
 *   son 파라미터 판정 — 파일의 숫자가 이 토글에 딸려 오는데 파일에는 토글이
 *     보이지 않습니다.
 *
 * `ctn_desc` 는 **적지 않습니다**. 여기서 손에 쥘 수 있는 것은
 * `RecipeInput.ctn_desc` 뿐인데 그것은 디바이스 설명문이 아니라 그 recipe 가
 * 걸린 **공정 스텝 이름**입니다(21ff6cf6 이 mock 을 사무실에 맞추면서 그렇게
 * 굳었습니다). 비교 화면의 `SummaryRow.ctn_desc` 는 진짜 디바이스 설명문이라,
 * 같은 이름으로 스텝 이름을 실어 보내면 읽는 사람이 둘을 맞대어 보게 됩니다.
 * 디바이스를 가리키는 것은 `lot_cd` 이고, 표의 첫 열도 그것입니다.
 */
const summaryRows = (input: ComplianceExportInput): (string | number)[][] => {
  const { health } = input
  const violationParams = health.recipes.reduce((sum, r) => sum + r.violation_params.length, 0)
  return [
    ['field', 'value'],
    ['lot_cd', health.lot_cd],
    ['판정 범위 recipe', health.recipes.length],
    ['판정 recipe', health.judged_recipes],
    ['상한 초과 recipe', health.violation_recipes],
    ['상한 초과 파라미터', violationParams],
    ['특수 job(판정 범위 밖)', input.exempt],
    ['son 파라미터 판정', input.judgeSons ? '포함' : '제외'],
    ['exported_at', input.exportedAt]
  ]
}

/** mother/son 열의 위치. `emphasize` 가 행에서 그 칸을 찾을 때 씁니다. */
const ROLE_COL = COMPLIANCE_HEADERS.indexOf(ROLE_HEADER)

/** mother 행을 굵게 띄웁니다 — image 의 주인이 한눈에 보이도록 (user 요청 2026-09-02). */
export const isMotherRow = (row: (string | number)[]): boolean => row[ROLE_COL] === 'mother'

export const buildComplianceWorkbook = (input: ComplianceExportInput): WorkbookSheet[] => [
  { name: '요약', rows: summaryRows(input) },
  { name: '판정', rows: judgementRows(input.health), emphasize: isMotherRow }
]

/**
 * `R0A8_rule_compliance_2026-09-01.xlsx`.
 *
 * 날짜를 **받는** 것은 룰을 고치면 같은 디바이스의 판정이 날마다 달라지기
 * 때문입니다 — 파일 이름이 언제의 판정인지 말합니다. 함수 안에서 시계를 읽지
 * 않는 것은 그래야 이름이 테스트 가능하기 때문입니다.
 */
export const complianceFileName = (lotCd: string, stamp: string): string =>
  `${safeFileNamePart(lotCd)}_rule_compliance_${stamp}.xlsx`
