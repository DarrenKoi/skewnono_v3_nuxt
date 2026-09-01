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
import { capCell, overCell, paramNoteCell, recipeVerdictCell } from './violationCells.ts'

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
  'measure_points',
  'cap',
  '상한 초과',
  '비고'
] as const

export interface ComplianceExportInput {
  /** 표가 이미 판정한 결과 그대로. 여기서 다시 판정하지 않습니다. */
  health: LotHealth
  ctn_desc: string
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
 * 구분할 수 없습니다 (lotParamExport 와 같은 결정).
 *
 * 판정이 없는 recipe 는 여기 올 수 없습니다 — 이 표는 룰이 있는 R3 만 다루고,
 * 판정 범위 밖 job 은 화면이 `evaluateLot` 에 넘기기 전에 이미 걸렀습니다.
 * 그래서 fallback 자리는 빈 문자열입니다.
 */
const judgementRows = (health: LotHealth): (string | number)[][] => {
  const rows: (string | number)[][] = [[...COMPLIANCE_HEADERS]]
  for (const recipe of health.recipes) {
    const verdict = recipeVerdictCell(recipe, '')
    if (recipe.results.length === 0) {
      rows.push([health.lot_cd, recipe.recipe_id, verdict, '', '', '', '', '파라미터 없음'])
      continue
    }
    for (const param of recipe.results) {
      rows.push([
        health.lot_cd,
        recipe.recipe_id,
        verdict,
        param.name,
        param.point_count,
        capCell(param),
        overCell(param),
        paramNoteCell(recipe, param, '')
      ])
    }
  }
  return rows
}

/** 슬라이드오버 머리말과 같은 숫자들. 거기 없는 것은 son 토글 한 줄뿐입니다 —
 *  파일의 숫자가 그 토글에 딸려 오는데, 파일에는 토글이 보이지 않습니다. */
const summaryRows = (input: ComplianceExportInput): (string | number)[][] => {
  const { health } = input
  const violationParams = health.recipes.reduce((sum, r) => sum + r.violation_params.length, 0)
  return [
    ['field', 'value'],
    ['lot_cd', health.lot_cd],
    ['ctn_desc', input.ctn_desc],
    ['recipe', health.recipes.length],
    ['판정 recipe', health.judged_recipes],
    ['상한 초과 recipe', health.violation_recipes],
    ['상한 초과 파라미터', violationParams],
    ['son 파라미터 판정', input.judgeSons ? '포함' : '제외'],
    ['exported_at', input.exportedAt]
  ]
}

export const buildComplianceWorkbook = (input: ComplianceExportInput): WorkbookSheet[] => [
  { name: '요약', rows: summaryRows(input) },
  { name: '판정', rows: judgementRows(input.health) }
]

/**
 * `R0A8_rule_compliance_2026-09-01.xlsx`.
 *
 * 날짜를 **받는** 것은 룰을 고치면 같은 디바이스의 판정이 날마다 달라지기
 * 때문입니다 — 파일 이름이 언제의 판정인지 말합니다. 함수 안에서 시계를 읽지
 * 않는 것은 그래야 이름이 테스트 가능하기 때문입니다.
 *
 * lot 코드는 office 값이라 파일명으로 쓰기 전에 씻어 냅니다
 * (lotParamExport.lotParamFileName 과 같은 이유).
 */
export const complianceFileName = (lotCd: string, stamp: string): string =>
  `${(lotCd || 'unknown').replace(/[^\w.-]+/g, '_')}_rule_compliance_${stamp}.xlsx`
