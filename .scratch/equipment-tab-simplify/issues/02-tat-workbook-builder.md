# 02 — TAT 장비별 워크북 빌더

Status: open
Plan: [`../plan.md`](../plan.md)
Blocked by: 01

TAT 탭의 장비별 결과를 시트 3개(`장비`/`레시피`/`일별추이`)로 조립하는 순수
함수입니다. 파일을 쓰지 않으므로 `node --test`로 전부 검증됩니다.

**Files:**

- Create: `front-dev-home/app/utils/equipmentExport.ts`
- Create: `front-dev-home/app/utils/equipmentExport.test.ts`

**Interfaces:**

- Consumes: `WorkbookSheet` (티켓 01, `./xlsx.ts`)
- Produces:

```ts
export interface TatEquipmentWorkbookInput {
  equipments: RecipeTatEquipmentRow[]
  compare: RecipeTatEquipmentCompareResponse | null
}
export function buildTatEquipmentWorkbook(
  input: TatEquipmentWorkbookInput
): WorkbookSheet[]
```

**시트 규격**

| 시트 | 헤더 |
| --- | --- |
| `장비` | `eqp_id`, `fab`, `model`, `exec_count`, `total_meastime_sec`, `avg_meastime_sec`, `recipe_count` |
| `레시피` | `full_name`, `total_meastime_sec`, 그리고 장비마다 `<eqp>_meas_counts`, `<eqp>_total_meastime_sec`, `<eqp>_avg_meastime_sec` |
| `일별추이` | `date`, 그리고 장비마다 `<eqp>_total_meastime_sec`, `<eqp>_exec_count` |

`compare`가 `null`이면 `장비` 시트 하나만 나옵니다(장비를 고르지 않은 상태).

미실행 칸은 건수·합계가 `0`, **평균은 빈 문자열**입니다. 0으로 채우면 "돌았는데
평균이 0초"로 읽힙니다.

---

- [ ] **Step 1: 실패하는 테스트를 쓴다**

Create `front-dev-home/app/utils/equipmentExport.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { buildTatEquipmentWorkbook } from './equipmentExport.ts'
import type {
  RecipeTatEquipmentRow,
  RecipeTatEquipmentCompareResponse
} from '~/composables/useRecipeTatApi'

// 판정 필드(tat_index, occupancy, usage_ratio)까지 채워둡니다 — 시트에
// **나오지 않아야** 한다는 것이 이 테스트가 지키는 성질이라, 값이 없으면
// 아무것도 증명하지 못합니다.
const equipment = (
  eqpId: string,
  over: Partial<RecipeTatEquipmentRow> = {}
): RecipeTatEquipmentRow => ({
  eqp_id: eqpId,
  fab_name: 'M14',
  eqp_model_cd: 'TP-5000',
  exec_count: 430,
  total_meastime: 8040,
  avg_meastime: 18.7,
  recipe_count: 12,
  top_recipe: 'QC/FAST_001',
  top_recipe_share: 0.42,
  tat_index: 1.08,
  occupancy: 0.62,
  usage_ratio: 1.13,
  ...over
})

const compare = (
  over: Partial<RecipeTatEquipmentCompareResponse> = {}
): RecipeTatEquipmentCompareResponse => ({
  tool_type: 'cd-sem',
  fab_names: ['M14'],
  start_date: '2026-08-01',
  end_date: '2026-08-02',
  eqp_ids: ['TP-1203', 'TP-1204'],
  trends: [
    {
      eqp_id: 'TP-1203',
      points: [
        { date: '2026-08-01', total_meastime: 3000, exec_count: 100 },
        { date: '2026-08-02', total_meastime: 5040, exec_count: 330 }
      ]
    },
    {
      eqp_id: 'TP-1204',
      points: [
        { date: '2026-08-01', total_meastime: 1000, exec_count: 40 },
        { date: '2026-08-02', total_meastime: 0, exec_count: 0 }
      ]
    }
  ],
  recipes: [
    {
      class_name: 'QC',
      recipe_name: 'FAST_001',
      full_name: 'QC/FAST_001',
      total_meastime: 6000,
      cells: [
        { eqp_id: 'TP-1203', meas_counts: 200, total_meastime: 4000, avg_meastime: 20 },
        { eqp_id: 'TP-1204', meas_counts: 100, total_meastime: 2000, avg_meastime: 20 }
      ]
    },
    {
      class_name: 'ADI',
      recipe_name: 'SLOW_002',
      full_name: 'ADI/SLOW_002',
      total_meastime: 3040,
      cells: [
        { eqp_id: 'TP-1203', meas_counts: 40, total_meastime: 3040, avg_meastime: 76 },
        // 돌지 않은 장비: 백엔드가 0으로 채워 보냅니다.
        { eqp_id: 'TP-1204', meas_counts: 0, total_meastime: 0, avg_meastime: 0 }
      ]
    }
  ],
  ...over
})

test('장비를 고르지 않으면 장비 시트 하나만 나온다', () => {
  const sheets = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1203')],
    compare: null
  })

  assert.deepEqual(sheets.map(s => s.name), ['장비'])
})

test('장비 시트에 지수·점유율·신호 열이 없다', () => {
  const [sheet] = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1203')],
    compare: null
  })

  assert.deepEqual(sheet!.rows[0], [
    'eqp_id', 'fab', 'model', 'exec_count',
    'total_meastime_sec', 'avg_meastime_sec', 'recipe_count'
  ])
  assert.deepEqual(sheet!.rows[1], ['TP-1203', 'M14', 'TP-5000', 430, 8040, 18.7, 12])
})

test('레시피 시트는 장비마다 세 열로 펼치고 미실행 평균은 빈 칸이다', () => {
  const sheets = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1203'), equipment('TP-1204')],
    compare: compare()
  })
  const sheet = sheets.find(s => s.name === '레시피')!

  assert.deepEqual(sheet.rows[0], [
    'full_name', 'total_meastime_sec',
    'TP-1203_meas_counts', 'TP-1203_total_meastime_sec', 'TP-1203_avg_meastime_sec',
    'TP-1204_meas_counts', 'TP-1204_total_meastime_sec', 'TP-1204_avg_meastime_sec'
  ])
  assert.deepEqual(sheet.rows[1], ['QC/FAST_001', 6000, 200, 4000, 20, 100, 2000, 20])
  // 돌지 않은 장비: 건수·합계는 0, 평균은 빈 칸.
  assert.deepEqual(sheet.rows[2], ['ADI/SLOW_002', 3040, 40, 3040, 76, 0, 0, ''])
})

test('일별추이 시트는 날짜마다 한 행이고 장비마다 두 열이다', () => {
  const sheets = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1203'), equipment('TP-1204')],
    compare: compare()
  })
  const sheet = sheets.find(s => s.name === '일별추이')!

  assert.deepEqual(sheet.rows[0], [
    'date',
    'TP-1203_total_meastime_sec', 'TP-1203_exec_count',
    'TP-1204_total_meastime_sec', 'TP-1204_exec_count'
  ])
  assert.deepEqual(sheet.rows[1], ['2026-08-01', 3000, 100, 1000, 40])
  assert.deepEqual(sheet.rows[2], ['2026-08-02', 5040, 330, 0, 0])
})

test('열 순서는 플릿 표가 아니라 응답의 eqp_ids 를 따른다', () => {
  // 플릿 표는 총 TAT 내림차순이라 선택 순서와 다를 수 있습니다. 매트릭스의
  // cells 는 eqp_ids 순서로 0채움되어 오므로, 헤더가 그 순서를 따르지 않으면
  // 열이 통째로 밀려 다른 장비의 숫자를 보여줍니다.
  const sheets = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1204'), equipment('TP-1203')],
    compare: compare()
  })
  const sheet = sheets.find(s => s.name === '레시피')!

  assert.equal(sheet.rows[0]![2], 'TP-1203_meas_counts')
})
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd front-dev-home && npx node --test "app/utils/equipmentExport.test.ts"`
Expected: FAIL — `Cannot find module './equipmentExport.ts'`

- [ ] **Step 3: 빌더를 구현한다**

Create `front-dev-home/app/utils/equipmentExport.ts`:

```ts
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
```

- [ ] **Step 4: 테스트 통과를 확인한다**

Run: `cd front-dev-home && npx node --test "app/utils/equipmentExport.test.ts"`
Expected: PASS 5건.

- [ ] **Step 5: 타입체크·린트**

Run:

```bash
cd front-dev-home
npm run typecheck
npm run lint
```

Expected: 통과.

- [ ] **Step 6: 커밋**

```bash
git add front-dev-home/app/utils/equipmentExport.ts \
        front-dev-home/app/utils/equipmentExport.test.ts
git commit -m "feat(front): TAT 장비별 워크북 빌더를 추가한다

장비/레시피/일별추이 세 시트를 조립하는 순수 함수입니다. 화면이 한 칸에
합쳐 보여주는 값을 장비마다 열로 풀고, 초 단위 원시 수치로 냅니다.

일별추이는 지금까지 어디서도 내보낼 수 없던 데이터입니다 — compare 응답에
이미 들어 있는데 차트로만 소비되고 있었습니다."
```
