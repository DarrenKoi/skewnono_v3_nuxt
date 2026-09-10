// 비교 페이지 "정렬" 칩의 어휘. **한 칩이 두 표면을 정합니다** — 위쪽 막대
// 차트(파라미터 비교)와 아래쪽 Lot 요약(카드·표·Excel).
//
// 이 모듈이 있는 이유가 그 "두 표면" 입니다. 예전에는 차트만 칩을 읽고
// (comparison.vue 의 sortedRows), Lot 요약은 자기 열 정렬 상태(health 순)를
// 따로 들고 있었습니다. 그래서 칩을 눌러 막대는 다시 늘어서는데 바로 아래 표는
// 그대로 있었고, 같은 화면의 두 목록이 서로 다른 순서로 같은 lot 들을 보여
// 줬습니다.
//
// 값 import 는 상대 경로 + 확장자로 유지합니다 — app/utils 관례대로 node --test
// 가 그대로 실행합니다 (lotHealth.ts 와 같은 방식).
import { paraTotal } from './lotHealth.ts'
import type { SummaryRow } from '~/composables/useRecipeStatisticsApi'

/**
 * 정렬 축.
 *
 *   default     lot 이름 오름차순. 값이 아니라 이름을 찾으러 온 사람용입니다.
 *   paraStack   파라미터 합계 내림차순. 막대가 긴 순서와 같습니다.
 *   availRecipe 운용 recipe 수 내림차순.
 *
 * 값 축 둘이 내림차순인 것은 두 축 모두 "많은 쪽이 볼 일" 이기 때문입니다 —
 * 파라미터가 많은 디바이스가 TAT 를 먹고, 운용 recipe 가 많은 디바이스가 관리
 * 대상입니다.
 */
export type LotSortKey = 'default' | 'paraStack' | 'availRecipe'

/**
 * 정렬에 필요한 최소 행. 요약 행과 그 파생(Profiled 등)이 모두 만족합니다.
 *
 * para 구간은 이름을 다시 적지 않고 `paraTotal` 의 인자 타입을 그대로 씁니다 —
 * 구간이 늘면(2026-08-10 의 para_over_16 처럼) 고칠 곳이 그 함수 하나입니다.
 */
type SortableLot = Parameters<typeof paraTotal>[0] & Pick<SummaryRow, 'lot_cd' | 'avail_recipe'>

/**
 * 칩 하나가 정하는 것 전부 — 무엇을 재는가, 어느 쪽이 위인가, 표의 어느 열인가.
 *
 * 셋을 한 자리에 적는 것이 요점입니다. 방향을 비교 함수와 열 상태에 따로 두면
 * 칩 하나를 오름차순으로 바꿀 때 한쪽만 고쳐도 아무 데서도 오류가 나지 않고,
 * 차트와 표가 반대로 늘어선 화면만 남습니다.
 *
 * `value: null` 은 값이 아니라 이름으로 세운다는 뜻입니다.
 *
 * `column` 은 Lot 요약 표(TanStack)의 열 id 입니다. 표는 자체 정렬 기능을 이미
 * 갖고 있으므로 행을 미리 정렬해 넘기는 대신 **그 상태를 칩으로 몹니다** —
 * 그래야 카드·표·Excel 세 표면이 지금처럼 `sorting` 한 곳만 읽는 구조로 남고,
 * 열 머리글을 눌러 칩에 없는 축(health·outlier …)으로 파고드는 길도 열려
 * 있습니다. 없는 열 id 를 주면 표가 조용히 정렬을 멈추므로, LotTable 이
 * 자기 열 목록에 대고 이 id 를 컴파일 시점에 확인합니다.
 */
export const LOT_SORT = {
  default: { value: null, desc: false, column: 'lot_cd' },
  paraStack: { value: paraTotal, desc: true, column: 'para_total' },
  availRecipe: { value: (row: SortableLot) => row.avail_recipe, desc: true, column: 'avail_recipe' }
} as const satisfies Record<
  LotSortKey,
  { value: ((row: SortableLot) => number) | null, desc: boolean, column: string }
>

/**
 * 칩 하나에 대응하는 비교 함수.
 *
 * 값이 같을 때 lot 이름으로 다시 가르는 것이 **load-bearing** 입니다. 동률을
 * 남겨 두면 순서가 입력 배열 순서에 딸려 오는데, 차트는 요약 행 배열을 그대로
 * 정렬하고 표는 TanStack 이 자기 행 모델을 정렬하므로 두 입력이 같다는 보장이
 * 없습니다. para 합계가 같은 lot 이 흔하다는 점(버킷이 좁을수록 흔합니다)을
 * 생각하면, 동률 규칙이 없으면 칩을 눌러 놓고도 위아래 순서가 어긋납니다.
 */
const lotComparator = <T extends SortableLot>(key: LotSortKey) => {
  const byName = (a: T, b: T) => a.lot_cd.localeCompare(b.lot_cd)
  const { value, desc } = LOT_SORT[key]
  if (!value) return byName
  const direction = desc ? -1 : 1
  return (a: T, b: T) => direction * (value(a) - value(b)) || byName(a, b)
}

/** 원본을 건드리지 않고 정렬된 사본을 돌려줍니다. */
export const sortLots = <T extends SortableLot>(rows: T[], key: LotSortKey): T[] =>
  [...rows].sort(lotComparator(key))
