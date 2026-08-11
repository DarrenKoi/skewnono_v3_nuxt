/**
 * 장비별 탭의 내보내기 워크북.
 *
 * 화면은 한 칸에 "건수 · 시간"을 합쳐 보여주지만 시트는 장비마다 열로 풉니다 —
 * 합쳐진 문자열은 스프레드시트에서 다시 쪼개야 하는 값입니다. 같은 이유로
 * 값은 화면 표기(`2h 14m`)가 아니라 초 단위 숫자로 내고, 단위는 열 이름에
 * 박습니다.
 *
 * 파일을 쓰지 않는 순수 함수입니다. 쓰는 쪽은 `./xlsx.ts` 이고, 그 분리선이
 * 곧 `node --test` 로 검증할 수 있는 범위의 경계입니다.
 */
import type { WorkbookSheet } from './xlsx.ts'
import type {
  FailIssueEquipmentRow,
  FailIssueEquipmentCompareResponse
} from '~/composables/useFailIssueApi'
import type {
  RecipeTatEquipmentRow,
  RecipeTatEquipmentCompareResponse
} from '~/composables/useRecipeTatApi'

// 미실행 칸의 파생값(평균·비율)은 0 이 아니라 빈 칸입니다. 0 은 "돌았는데
// 평균이 0초"로 읽히고, 그건 이 표가 절대 말해서는 안 되는 문장입니다.
const BLANK = ''

const EQUIPMENT_HEADERS = [
  'eqp_id', 'fab', 'model', 'exec_count',
  'total_meastime_sec', 'avg_meastime_sec', 'recipe_count'
]

export interface TatEquipmentWorkbookInput {
  /** 플릿 표에 실제로 보이는 행(검색·정렬 적용 후). */
  equipments: RecipeTatEquipmentRow[]
  /** 장비를 고르지 않았으면 null — 그때는 `장비` 시트만 나옵니다. */
  compare: RecipeTatEquipmentCompareResponse | null
}

export function buildTatEquipmentWorkbook(
  input: TatEquipmentWorkbookInput
): WorkbookSheet[] {
  const sheets: WorkbookSheet[] = [{
    name: '장비',
    rows: [
      EQUIPMENT_HEADERS,
      ...input.equipments.map(row => [
        row.eqp_id,
        row.fab_name,
        row.eqp_model_cd,
        row.exec_count,
        row.total_meastime,
        row.avg_meastime,
        row.recipe_count
      ])
    ]
  }]

  const compare = input.compare
  if (!compare) return sheets

  // 열 순서는 응답의 eqp_ids 입니다. cells 가 그 순서로 0채움되어 오므로
  // 인덱스로 바로 꽂습니다 — 다른 순서를 쓰면 열이 밀려 다른 장비의 숫자를
  // 보여주게 되고, 그 어긋남은 조용합니다.
  const eqpIds = compare.eqp_ids

  sheets.push({
    name: '레시피',
    rows: [
      [
        'full_name', 'total_meastime_sec',
        ...eqpIds.flatMap(id => [
          `${id}_meas_counts`, `${id}_total_meastime_sec`, `${id}_avg_meastime_sec`
        ])
      ],
      ...compare.recipes.map(recipe => [
        recipe.full_name,
        recipe.total_meastime,
        ...eqpIds.flatMap((_, index) => {
          const cell = recipe.cells[index]
          if (!cell || cell.meas_counts === 0) return [0, 0, BLANK]
          return [cell.meas_counts, cell.total_meastime, cell.avg_meastime]
        })
      ])
    ]
  })

  // 날짜 축은 첫 시리즈에서 가져옵니다. 백엔드가 조회 기간의 모든 날짜를
  // 모든 장비에 대해 0채움하므로(`days_in_range`) 시리즈끼리 길이가 같습니다.
  const dates = compare.trends[0]?.points.map(point => point.date) ?? []

  sheets.push({
    name: '일별추이',
    rows: [
      [
        'date',
        ...eqpIds.flatMap(id => [`${id}_total_meastime_sec`, `${id}_exec_count`])
      ],
      ...dates.map((date, dayIndex) => [
        date,
        ...eqpIds.flatMap((id) => {
          const point = compare.trends
            .find(series => series.eqp_id === id)?.points[dayIndex]
          return [point?.total_meastime ?? 0, point?.exec_count ?? 0]
        })
      ])
    ]
  })

  return sheets
}

export type FailSection = 'align' | 'meas'

/** 0..1 비율을 소수 둘째 자리 퍼센트 **숫자**로. 문자열로 내면 스프레드시트가
 *  다시 숫자로 바꿔야 합니다. */
const asPercent = (rate: number) => Number((rate * 100).toFixed(2))

export interface FailEquipmentWorkbookInput {
  /** 플릿 표에 실제로 보이는 행(검색·정렬 적용 후). */
  equipments: FailIssueEquipmentRow[]
  /** 장비를 고르지 않았으면 null. */
  compare: FailIssueEquipmentCompareResponse | null
  /** 보고 있는 축. 응답은 둘 다 담고 있지만 파일에는 이쪽만 나갑니다. */
  section: FailSection
}

export function buildFailEquipmentWorkbook(
  input: FailEquipmentWorkbookInput
): WorkbookSheet[] {
  const isAlign = input.section === 'align'
  const axis = isAlign ? 'align' : 'meas'

  const sheets: WorkbookSheet[] = [{
    name: '장비',
    rows: [
      [
        'eqp_id', 'fab', 'model', 'exec_count',
        `${axis}_fail_count`, `${axis}_fail_rate_pct`, 'recipe_count'
      ],
      ...input.equipments.map(row => [
        row.eqp_id,
        row.fab_name,
        row.eqp_model_cd,
        row.exec_count,
        isAlign ? row.align_fail_count : row.meas_fail_count,
        asPercent(isAlign ? row.align_fail_rate : row.meas_fail_rate),
        row.recipe_count
      ])
    ]
  }]

  const compare = input.compare
  if (!compare) return sheets

  const eqpIds = compare.eqp_ids

  // 화면이 활성 축으로 다시 정렬하므로 파일도 같은 순서여야 합니다. 백엔드
  // 순서는 두 축의 합이라 어느 탭에서도 그대로는 맞지 않습니다.
  const recipes = [...compare.recipes].sort((a, b) =>
    (isAlign ? b.total_align_fail_count : b.total_meas_fail_count)
    - (isAlign ? a.total_align_fail_count : a.total_meas_fail_count))

  sheets.push({
    name: '레시피',
    rows: [
      [
        'full_name', 'total_exec_count', `total_${axis}_fail_count`,
        ...eqpIds.flatMap(id => [
          `${id}_exec_count`, `${id}_${axis}_fail_count`, `${id}_${axis}_fail_rate_pct`
        ])
      ],
      ...recipes.map(recipe => [
        recipe.full_name,
        recipe.total_exec_count,
        isAlign ? recipe.total_align_fail_count : recipe.total_meas_fail_count,
        ...eqpIds.flatMap((_, index) => {
          const cell = recipe.cells[index]
          if (!cell || cell.exec_count === 0) return [0, 0, BLANK]
          const fails = isAlign ? cell.align_fail_count : cell.meas_fail_count
          return [cell.exec_count, fails, asPercent(fails / cell.exec_count)]
        })
      ])
    ]
  })

  const dates = compare.trends[0]?.points.map(point => point.date) ?? []

  sheets.push({
    name: '일별추이',
    rows: [
      [
        'date',
        ...eqpIds.flatMap(id => [`${id}_exec_count`, `${id}_${axis}_fail_count`])
      ],
      ...dates.map((date, dayIndex) => [
        date,
        ...eqpIds.flatMap((id) => {
          const point = compare.trends
            .find(series => series.eqp_id === id)?.points[dayIndex]
          if (!point) return [0, 0]
          return [
            point.exec_count,
            isAlign ? point.align_fail_count : point.meas_fail_count
          ]
        })
      ])
    ]
  })

  return sheets
}
